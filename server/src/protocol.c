#include "protocol.h"
#include "logger.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <time.h>
#include <sys/socket.h>
#include <unistd.h>
#include <netdb.h>

#define MAX_SENSORS 256
#define MAX_OPERATORS 64
#define SENSOR_ID_LEN 64
#define LOCATION_LEN 128

typedef struct {
    char id[SENSOR_ID_LEN];
    char type[32];
    char location[LOCATION_LEN];
    double last_value;
    time_t last_ts;
    int active;
} sensor_t;

typedef struct {
    int sock;
    char user[64];
    int authenticated;
} operator_t;

static sensor_t sensors[MAX_SENSORS];
static int num_sensors = 0;
static operator_t operators[MAX_OPERATORS];
static int num_operators = 0;
static pthread_mutex_t state_mutex = PTHREAD_MUTEX_INITIALIZER;

static const double THRESHOLD_TEMP_MAX = 40.0;
static const double THRESHOLD_HUMIDITY_MAX = 90.0;
static const double THRESHOLD_PRESSURE_MIN = 1000.0;
static const double THRESHOLD_PRESSURE_MAX = 1020.0;
static const double THRESHOLD_VIBRATION_MAX = 10.0;
static const double THRESHOLD_CONSUMO_MAX = 5000.0;

static int is_operator_socket(int sock) {
    for (int i = 0; i < num_operators; i++) {
        if (operators[i].sock == sock) return 1;
    }
    return 0;
}

static void add_operator(int sock) {
    pthread_mutex_lock(&state_mutex);
    if (num_operators < MAX_OPERATORS) {
        operators[num_operators].sock = sock;
        operators[num_operators].user[0] = '\0';
        operators[num_operators].authenticated = 0;
        num_operators++;
    }
    pthread_mutex_unlock(&state_mutex);
}

static void remove_operator(int sock) {
    pthread_mutex_lock(&state_mutex);
    for (int i = 0; i < num_operators; i++) {
        if (operators[i].sock == sock) {
            operators[i] = operators[num_operators - 1];
            num_operators--;
            break;
        }
    }
    pthread_mutex_unlock(&state_mutex);
}

static void set_operator_authenticated(int sock, const char *user) {
    pthread_mutex_lock(&state_mutex);
    for (int i = 0; i < num_operators; i++) {
        if (operators[i].sock == sock) {
            operators[i].authenticated = 1;
            strncpy(operators[i].user, user, sizeof(operators[i].user) - 1);
            operators[i].user[sizeof(operators[i].user) - 1] = '\0';
            break;
        }
    }
    pthread_mutex_unlock(&state_mutex);
}

static int operator_authenticated(int sock) {
    int auth = 0;
    pthread_mutex_lock(&state_mutex);
    for (int i = 0; i < num_operators; i++) {
        if (operators[i].sock == sock) {
            auth = operators[i].authenticated;
            break;
        }
    }
    pthread_mutex_unlock(&state_mutex);
    return auth;
}

static int auth_validate(const char *user, const char *password);

static void broadcast_to_operators(const char *msg, int exclude_sock) {
    char buf[MAX_MSG_LEN + 4];
    snprintf(buf, sizeof(buf), "%s\r\n", msg);
    pthread_mutex_lock(&state_mutex);
    for (int i = 0; i < num_operators; i++) {
        if (operators[i].sock != exclude_sock && operators[i].authenticated) {
            send(operators[i].sock, buf, (size_t)strlen(buf), 0);
        }
    }
    pthread_mutex_unlock(&state_mutex);
}

void parse_message(const char *line, parsed_msg_t *out) {
    out->cmd = CMD_UNKNOWN;
    out->nfields = 0;
    char copy[MAX_MSG_LEN];
    strncpy(copy, line, sizeof(copy) - 1);
    copy[sizeof(copy) - 1] = '\0';
    char *p = copy;
    while (out->nfields < MAX_FIELDS) {
        char *sep = strchr(p, '|');
        if (sep) *sep = '\0';
        while (*p == ' ' || *p == '\t') p++;
        char *end = p + strlen(p);
        while (end > p && (end[-1] == ' ' || end[-1] == '\t' || end[-1] == '\r' || end[-1] == '\n')) *--end = '\0';
        if (*p) {
            out->fields[out->nfields] = strdup(p);
            out->nfields++;
        }
        if (!sep) break;
        p = sep + 1;
    }
    if (out->nfields >= 1) {
        if (strcmp(out->fields[0], "REGISTER") == 0) out->cmd = CMD_REGISTER;
        else if (strcmp(out->fields[0], "MEASUREMENT") == 0) out->cmd = CMD_MEASUREMENT;
        else if (strcmp(out->fields[0], "LOGIN") == 0) out->cmd = CMD_LOGIN;
        else if (strcmp(out->fields[0], "QUERY_STATUS") == 0) out->cmd = CMD_QUERY_STATUS;
        else if (strcmp(out->fields[0], "QUERY_SENSORS") == 0) out->cmd = CMD_QUERY_SENSORS;
    }
}

void free_parsed(parsed_msg_t *p) {
    for (int i = 0; i < p->nfields; i++) {
        free(p->fields[i]);
        p->fields[i] = NULL;
    }
    p->nfields = 0;
}

static int check_anomaly(const char *type, double value, double *threshold, char *msg, size_t msg_len) {
    if (strcmp(type, "temperatura") == 0) {
        if (value > THRESHOLD_TEMP_MAX) {
            *threshold = THRESHOLD_TEMP_MAX;
            snprintf(msg, msg_len, "Temperatura sobre umbral");
            return 1;
        }
    } else if (strcmp(type, "humedad") == 0) {
        if (value > THRESHOLD_HUMIDITY_MAX) {
            *threshold = THRESHOLD_HUMIDITY_MAX;
            snprintf(msg, msg_len, "Humedad sobre umbral");
            return 1;
        }
    } else if (strcmp(type, "presion") == 0) {
        if (value < THRESHOLD_PRESSURE_MIN) {
            *threshold = THRESHOLD_PRESSURE_MIN;
            snprintf(msg, msg_len, "Presion bajo umbral");
            return 1;
        }
        if (value > THRESHOLD_PRESSURE_MAX) {
            *threshold = THRESHOLD_PRESSURE_MAX;
            snprintf(msg, msg_len, "Presion sobre umbral");
            return 1;
        }
    } else if (strcmp(type, "vibracion") == 0) {
        if (value > THRESHOLD_VIBRATION_MAX) {
            *threshold = THRESHOLD_VIBRATION_MAX;
            snprintf(msg, msg_len, "Vibracion sobre umbral");
            return 1;
        }
    } else if (strcmp(type, "consumo") == 0) {
        if (value > THRESHOLD_CONSUMO_MAX) {
            *threshold = THRESHOLD_CONSUMO_MAX;
            snprintf(msg, msg_len, "Consumo sobre umbral");
            return 1;
        }
    }
    return 0;
}

const char *process_command(parsed_msg_t *p, int client_sock, const char *client_ip, int client_port) {
    (void)client_ip;
    (void)client_port;
    static char response[MAX_MSG_LEN];
    response[0] = '\0';

    if (p->cmd == CMD_UNKNOWN) {
        snprintf(response, sizeof(response), "ERROR|INVALID_MSG|Comando desconocido");
        return response;
    }

    if (p->cmd == CMD_LOGIN || p->cmd == CMD_QUERY_STATUS || p->cmd == CMD_QUERY_SENSORS) {
        if (!is_operator_socket(client_sock))
            add_operator(client_sock);
    }

    switch (p->cmd) {
        case CMD_REGISTER: {
            if (p->nfields != 4) {
                snprintf(response, sizeof(response), "ERROR|INVALID_MSG|REGISTER requiere tipo|id|ubicacion");
                return response;
            }
            const char *tipo = p->fields[1];
            const char *id = p->fields[2];
            const char *ubic = p->fields[3];
            pthread_mutex_lock(&state_mutex);
            for (int i = 0; i < num_sensors; i++) {
                if (sensors[i].active && strcmp(sensors[i].id, id) == 0) {
                    pthread_mutex_unlock(&state_mutex);
                    snprintf(response, sizeof(response), "ERROR|SENSOR_DUPLICATE|%s", id);
                    return response;
                }
            }
            if (num_sensors >= MAX_SENSORS) {
                pthread_mutex_unlock(&state_mutex);
                snprintf(response, sizeof(response), "ERROR|INVALID_MSG|Max sensores alcanzado");
                return response;
            }
            sensor_t *s = &sensors[num_sensors++];
            strncpy(s->id, id, SENSOR_ID_LEN - 1);
            s->id[SENSOR_ID_LEN - 1] = '\0';
            strncpy(s->type, tipo, sizeof(s->type) - 1);
            s->type[sizeof(s->type) - 1] = '\0';
            strncpy(s->location, ubic, LOCATION_LEN - 1);
            s->location[LOCATION_LEN - 1] = '\0';
            s->last_value = 0;
            s->last_ts = 0;
            s->active = 1;
            pthread_mutex_unlock(&state_mutex);
            snprintf(response, sizeof(response), "OK|REGISTER|%s", id);
            return response;
        }
        case CMD_MEASUREMENT: {
            if (p->nfields != 5) {
                snprintf(response, sizeof(response), "ERROR|INVALID_MSG|MEASUREMENT requiere id|tipo|valor|timestamp");
                return response;
            }
            const char *id = p->fields[1];
            const char *tipo = p->fields[2];
            double valor = atof(p->fields[3]);
            time_t ts = (time_t)atol(p->fields[4]);
            pthread_mutex_lock(&state_mutex);
            sensor_t *s = NULL;
            for (int i = 0; i < num_sensors; i++) {
                if (sensors[i].active && strcmp(sensors[i].id, id) == 0) {
                    s = &sensors[i];
                    break;
                }
            }
            if (!s) {
                pthread_mutex_unlock(&state_mutex);
                snprintf(response, sizeof(response), "ERROR|INVALID_MSG|Sensor no registrado");
                return response;
            }
            s->last_value = valor;
            s->last_ts = ts;
            pthread_mutex_unlock(&state_mutex);
            snprintf(response, sizeof(response), "OK|MEASUREMENT|%s", id);
            double thresh = 0;
            char alert_msg[256];
            if (check_anomaly(tipo, valor, &thresh, alert_msg, sizeof(alert_msg))) {
                char alert_line[MAX_MSG_LEN];
                snprintf(alert_line, sizeof(alert_line), "ALERT|%s|%s|%.2f|%.2f|%s", id, tipo, valor, thresh, alert_msg);
                broadcast_to_operators(alert_line, -1);
            }
            char meas_broadcast[MAX_MSG_LEN];
            snprintf(meas_broadcast, sizeof(meas_broadcast), "MEASUREMENT|%s|%s|%.2f|%ld", id, tipo, valor, (long)ts);
            broadcast_to_operators(meas_broadcast, -1);
            return response;
        }
        case CMD_LOGIN: {
            if (p->nfields != 3) {
                snprintf(response, sizeof(response), "ERROR|INVALID_MSG|LOGIN requiere usuario|password");
                return response;
            }
            const char *user = p->fields[1];
            const char *pass = p->fields[2];
            if (auth_validate(user, pass)) {
                set_operator_authenticated(client_sock, user);
                snprintf(response, sizeof(response), "OK|LOGIN|%s", user);
            } else {
                snprintf(response, sizeof(response), "ERROR|AUTH_FAILED|Credenciales invalidas");
            }
            return response;
        }
        case CMD_QUERY_STATUS: {
            if (!operator_authenticated(client_sock)) {
                snprintf(response, sizeof(response), "ERROR|NOT_AUTHENTICATED|Login requerido");
                return response;
            }
            pthread_mutex_lock(&state_mutex);
            int n = 0;
            for (int i = 0; i < num_sensors; i++) if (sensors[i].active) n++;
            pthread_mutex_unlock(&state_mutex);
            snprintf(response, sizeof(response), "OK|QUERY_STATUS|sensores_activos=%d", n);
            return response;
        }
        case CMD_QUERY_SENSORS: {
            if (!operator_authenticated(client_sock)) {
                snprintf(response, sizeof(response), "ERROR|NOT_AUTHENTICATED|Login requerido");
                return response;
            }
            char list[MAX_MSG_LEN];
            list[0] = '\0';
            pthread_mutex_lock(&state_mutex);
            for (int i = 0; i < num_sensors; i++) {
                if (!sensors[i].active) continue;
                char part[256];
                snprintf(part, sizeof(part), "%s,%s,%s", sensors[i].id, sensors[i].type, sensors[i].location);
                if (strlen(list) + strlen(part) + 2 < sizeof(list)) {
                    if (list[0]) strcat(list, ";");
                    strcat(list, part);
                }
            }
            pthread_mutex_unlock(&state_mutex);
            size_t max_list = sizeof(response) - 14;  /* "SENSOR_LIST|" = 13 + null */
            if (strlen(list) >= max_list)
                list[max_list] = '\0';
            snprintf(response, sizeof(response), "SENSOR_LIST|%s", list);
            return response;
        }
        default:
            snprintf(response, sizeof(response), "ERROR|INVALID_MSG|Comando no implementado");
            return response;
    }
}

void protocol_remove_client(int sock) {
    remove_operator(sock);
}

static char auth_host[256] = "localhost";
static char auth_port[8] = "5000";

void protocol_set_auth_host(const char *host, const char *port) {
    strncpy(auth_host, host ? host : "localhost", sizeof(auth_host) - 1);
    strncpy(auth_port, port ? port : "5000", sizeof(auth_port) - 1);
}

static int auth_validate(const char *user, const char *password) {
    struct addrinfo hints, *res = NULL;
    int sock = -1;
    int ret = 0;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    int gai = getaddrinfo(auth_host, auth_port, &hints, &res);
    if (gai != 0 || !res) {
        return 0;
    }
    sock = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (sock < 0) {
        if (res) freeaddrinfo(res);
        return 0;
    }
    if (connect(sock, res->ai_addr, res->ai_addrlen) < 0) {
        close(sock);
        freeaddrinfo(res);
        return 0;
    }
    freeaddrinfo(res);
    char req[1024];
    snprintf(req, sizeof(req),
             "GET /validate?user=%s&password=%s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\n\r\n",
             user, password, auth_host);
    if (send(sock, req, strlen(req), 0) < (ssize_t)strlen(req)) {
        close(sock);
        return 0;
    }
    char buf[512];
    ssize_t n = recv(sock, buf, sizeof(buf) - 1, 0);
    close(sock);
    if (n <= 0) return 0;
    buf[n] = '\0';
    if (strstr(buf, "200 OK") && strstr(buf, "valid=true")) ret = 1;
    return ret;
}

#ifndef PROTOCOL_H
#define PROTOCOL_H

#define MAX_MSG_LEN 1024
#define MAX_FIELDS 8

typedef enum {
    CMD_UNKNOWN,
    CMD_REGISTER,
    CMD_MEASUREMENT,
    CMD_LOGIN,
    CMD_QUERY_STATUS,
    CMD_QUERY_SENSORS
} command_t;

typedef struct {
    command_t cmd;
    int nfields;
    char *fields[MAX_FIELDS];
} parsed_msg_t;

void parse_message(const char *line, parsed_msg_t *out);
void free_parsed(parsed_msg_t *p);
const char *process_command(parsed_msg_t *p, int client_sock, const char *client_ip, int client_port);
void protocol_remove_client(int sock);
void protocol_set_auth_host(const char *host, const char *port);

#endif

#define _POSIX_C_SOURCE 200809L
#include "logger.h"
#include "protocol.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <errno.h>

#define LISTEN_BACKLOG 64
#define LINE_BUF_SIZE 1024

typedef struct {
    int sock;
    char ip[INET6_ADDRSTRLEN];
    int port;
} client_ctx_t;

static void *client_thread(void *arg) {
    client_ctx_t *ctx = (client_ctx_t *)arg;
    int sock = ctx->sock;
    char ip[INET6_ADDRSTRLEN];
    int port = ctx->port;
    strncpy(ip, ctx->ip, sizeof(ip));
    free(ctx);

    char line[LINE_BUF_SIZE];
    size_t pos = 0;

    while (1) {
        char c;
        ssize_t n = recv(sock, &c, 1, 0);
        if (n <= 0) break;
        if (pos < sizeof(line) - 1) {
            line[pos++] = c;
            line[pos] = '\0';
        }
        if (c == '\n') {
            if (pos > 0) {
                if (line[pos - 1] == '\n') line[--pos] = '\0';
                if (pos > 0 && line[pos - 1] == '\r') line[--pos] = '\0';
                parsed_msg_t parsed;
                parse_message(line, &parsed);
                log_request(ip, port, line);
                const char *resp = process_command(&parsed, sock, ip, port);
                log_response(ip, port, resp);
                char out[LINE_BUF_SIZE + 4];
                snprintf(out, sizeof(out), "%s\r\n", resp);
                send(sock, out, strlen(out), 0);
                free_parsed(&parsed);
            }
            pos = 0;
        }
    }

    protocol_remove_client(sock);
    close(sock);
    return NULL;
}

int main(int argc, char *argv[]) {
    if (argc < 3) {
        fprintf(stderr, "Uso: %s puerto archivoDeLogs [auth_host [auth_port]]\n", argv[0]);
        return 1;
    }
    const char *port_str = argv[1];
    const char *logfile = argv[2];
    const char *auth_host = argc > 3 ? argv[3] : "localhost";
    const char *auth_port = argc > 4 ? argv[4] : "5000";

    logger_init(logfile);
    protocol_set_auth_host(auth_host, auth_port);

    struct addrinfo hints, *res = NULL;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    hints.ai_flags = AI_PASSIVE;
    int gai = getaddrinfo(NULL, port_str, &hints, &res);
    if (gai != 0) {
        fprintf(stderr, "getaddrinfo: %s\n", gai_strerror(gai));
        log_error("0.0.0.0", 0, "getaddrinfo failed");
        logger_close();
        return 1;
    }

    int listen_fd = -1;
    struct addrinfo *rp;
    for (rp = res; rp != NULL; rp = rp->ai_next) {
        listen_fd = socket(rp->ai_family, rp->ai_socktype, rp->ai_protocol);
        if (listen_fd < 0) continue;
        int opt = 1;
        setsockopt(listen_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
        if (bind(listen_fd, rp->ai_addr, rp->ai_addrlen) == 0) break;
        close(listen_fd);
        listen_fd = -1;
    }
    freeaddrinfo(res);
    if (listen_fd < 0) {
        fprintf(stderr, "No se pudo bind al puerto %s\n", port_str);
        logger_close();
        return 1;
    }
    if (listen(listen_fd, LISTEN_BACKLOG) < 0) {
        perror("listen");
        logger_close();
        return 1;
    }
    printf("Servidor escuchando en puerto %s. Log: %s\n", port_str, logfile);

    while (1) {
        struct sockaddr_storage peer_addr;
        socklen_t peer_len = sizeof(peer_addr);
        int client_fd = accept(listen_fd, (struct sockaddr *)&peer_addr, &peer_len);
        if (client_fd < 0) {
            perror("accept");
            continue;
        }
        char ip[INET6_ADDRSTRLEN];
        int port = 0;
        if (peer_addr.ss_family == AF_INET) {
            struct sockaddr_in *in = (struct sockaddr_in *)&peer_addr;
            inet_ntop(AF_INET, &in->sin_addr, ip, sizeof(ip));
            port = ntohs(in->sin_port);
        } else {
            struct sockaddr_in6 *in6 = (struct sockaddr_in6 *)&peer_addr;
            inet_ntop(AF_INET6, &in6->sin6_addr, ip, sizeof(ip));
            port = ntohs(in6->sin6_port);
        }
        client_ctx_t *ctx = malloc(sizeof(client_ctx_t));
        if (!ctx) {
            close(client_fd);
            continue;
        }
        ctx->sock = client_fd;
        strncpy(ctx->ip, ip, sizeof(ctx->ip) - 1);
        ctx->ip[sizeof(ctx->ip) - 1] = '\0';
        ctx->port = port;
        pthread_t th;
        pthread_create(&th, NULL, client_thread, ctx);
        pthread_detach(th);
    }
    logger_close();
    return 0;
}

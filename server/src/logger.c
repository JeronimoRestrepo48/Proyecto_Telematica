#include "logger.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <pthread.h>

static FILE *log_file = NULL;
static pthread_mutex_t log_mutex = PTHREAD_MUTEX_INITIALIZER;

static void timestamp(char *buf, size_t bufsize) {
    time_t now = time(NULL);
    struct tm *t = localtime(&now);
    strftime(buf, bufsize, "%Y-%m-%d %H:%M:%S", t);
}

void logger_init(const char *logfile) {
    pthread_mutex_lock(&log_mutex);
    if (log_file) fclose(log_file);
    log_file = fopen(logfile, "a");
    if (!log_file) {
        fprintf(stderr, "No se pudo abrir archivo de log: %s\n", logfile);
    }
    pthread_mutex_unlock(&log_mutex);
}

void logger_close(void) {
    pthread_mutex_lock(&log_mutex);
    if (log_file) {
        fclose(log_file);
        log_file = NULL;
    }
    pthread_mutex_unlock(&log_mutex);
}

static void write_log(const char *level, const char *client_ip, int client_port, const char *msg) {
    char ts[64];
    timestamp(ts, sizeof(ts));
    pthread_mutex_lock(&log_mutex);
    printf("[%s] %s %s:%d - %s\n", ts, level, client_ip, client_port, msg);
    if (log_file) {
        fprintf(log_file, "[%s] %s %s:%d - %s\n", ts, level, client_ip, client_port, msg);
        fflush(log_file);
    }
    pthread_mutex_unlock(&log_mutex);
}

void log_request(const char *client_ip, int client_port, const char *message) {
    write_log("REQUEST", client_ip, client_port, message);
}

void log_response(const char *client_ip, int client_port, const char *response) {
    write_log("RESPONSE", client_ip, client_port, response);
}

void log_error(const char *client_ip, int client_port, const char *message) {
    write_log("ERROR", client_ip, client_port, message);
}

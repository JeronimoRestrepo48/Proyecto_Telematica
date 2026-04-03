#ifndef LOGGER_H
#define LOGGER_H

void logger_init(const char *logfile);
void logger_close(void);
void log_request(const char *client_ip, int client_port, const char *message);
void log_response(const char *client_ip, int client_port, const char *response);
void log_error(const char *client_ip, int client_port, const char *message);

#endif

FROM ubuntu:22.04
RUN apt-get update && apt-get install -y gcc make
WORKDIR /app
COPY . .
RUN make
EXPOSE 8888
CMD ["./server", "8888", "/app/server.log", "172.17.0.1", "5000"]
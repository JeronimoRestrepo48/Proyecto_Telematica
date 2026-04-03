import java.io.*;
import java.net.*;
import java.util.*;
import java.util.concurrent.*;

/**
 * Simulador de sensor IoT en Java.
 * Se conecta al servidor por nombre de dominio (resolución DNS),
 * registra el sensor y envía mediciones periódicas.
 */
public class SensorSimulator {
    private final String host;
    private final int port;
    private final String sensorType;
    private final String sensorId;
    private final String location;
    private final double intervalSec;
    private Socket socket;
    private BufferedReader reader;
    private PrintWriter writer;
    private volatile boolean running = true;

    public SensorSimulator(String host, int port, String sensorType, String sensorId, String location, double intervalSec) {
        this.host = host;
        this.port = port;
        this.sensorType = sensorType;
        this.sensorId = sensorId != null ? sensorId : "sensor_java_" + sensorType + "_" + (1000 + new Random().nextInt(9000));
        this.location = location;
        this.intervalSec = intervalSec;
    }

    private void connect() throws IOException {
        InetSocketAddress addr = new InetSocketAddress(host, port);
        socket = new Socket();
        socket.connect(addr, 10000);
        socket.setSoTimeout(10000);
        reader = new BufferedReader(new InputStreamReader(socket.getInputStream(), "UTF-8"));
        writer = new PrintWriter(new OutputStreamWriter(socket.getOutputStream(), "UTF-8"), true);
    }

    private String readLine() throws IOException {
        StringBuilder sb = new StringBuilder();
        int c;
        while ((c = reader.read()) != -1) {
            if (c == '\n') break;
            if (c != '\r') sb.append((char) c);
        }
        return sb.toString().trim();
    }

    private String sendCommand(String cmd) throws IOException {
        writer.println(cmd);
        return readLine();
    }

    private static final Map<String, double[]> RANGES = new HashMap<>();
    static {
        RANGES.put("temperatura", new double[]{15.0, 45.0});
        RANGES.put("humedad", new double[]{30.0, 95.0});
        RANGES.put("presion", new double[]{1005.0, 1025.0});
        RANGES.put("vibracion", new double[]{0.0, 12.0});
        RANGES.put("consumo", new double[]{100.0, 5200.0});
    }

    public void run() {
        Random rnd = new Random();
        double[] range = RANGES.getOrDefault(sensorType, new double[]{0.0, 100.0});
        double lo = range[0], hi = range[1];

        while (running) {
            try {
                connect();
            } catch (IOException e) {
                System.err.println("Error de conexión (resolución o red): " + e.getMessage() + ". Reintento en 5s...");
                try { Thread.sleep(5000); } catch (InterruptedException ie) { Thread.currentThread().interrupt(); break; }
                continue;
            }

            try {
                String resp = sendCommand("REGISTER|" + sensorType + "|" + sensorId + "|" + location);
                if (resp == null || !resp.startsWith("OK|REGISTER")) {
                    System.err.println("Registro fallido: " + resp);
                    close();
                    try { Thread.sleep(5000); } catch (InterruptedException ie) { break; }
                    continue;
                }
                System.out.println("Registrado: " + sensorId + " (" + sensorType + ") en " + location);
            } catch (IOException e) {
                System.err.println("Error en registro: " + e.getMessage());
                close();
                try { Thread.sleep(5000); } catch (InterruptedException ie) { break; }
                continue;
            }

            while (running) {
                try {
                    Thread.sleep((long) (intervalSec * 1000));
                    double value;
                    if (rnd.nextDouble() < 0.9) {
                        value = Math.round((lo + (hi - lo) * rnd.nextDouble()) * 100.0) / 100.0;
                    } else {
                        value = Math.round((lo + (hi * 1.2 - lo) * rnd.nextDouble()) * 100.0) / 100.0;
                    }
                    long ts = System.currentTimeMillis() / 1000;
                    String resp = sendCommand("MEASUREMENT|" + sensorId + "|" + sensorType + "|" + value + "|" + ts);
                    if (resp == null || !resp.startsWith("OK")) {
                        System.err.println("Medición rechazada: " + resp);
                    } else {
                        System.out.println("Enviado: " + value + " @ " + ts + " -> " + (resp.length() > 50 ? resp.substring(0, 50) + "..." : resp));
                    }
                } catch (IOException e) {
                    System.err.println("Conexión perdida: " + e.getMessage());
                    break;
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
            close();
            if (running) {
                System.out.println("Reconectando en 5s...");
                try { Thread.sleep(5000); } catch (InterruptedException ie) { break; }
            }
        }
    }

    private void close() {
        try {
            if (reader != null) reader.close();
            if (writer != null) writer.close();
            if (socket != null) socket.close();
        } catch (IOException ignored) {}
        reader = null;
        writer = null;
        socket = null;
    }

    public void stop() {
        running = false;
    }

    public static void main(String[] args) {
        String host = "localhost";
        int port = 8888;
        String type = "humedad";
        String id = null;
        String location = "Ubicacion Java";
        double interval = 5.0;
        for (int i = 0; i < args.length; i++) {
            if ("--host".equals(args[i]) && i + 1 < args.length) host = args[++i];
            else if ("--port".equals(args[i]) && i + 1 < args.length) port = Integer.parseInt(args[++i]);
            else if ("--type".equals(args[i]) && i + 1 < args.length) type = args[++i];
            else if ("--id".equals(args[i]) && i + 1 < args.length) id = args[++i];
            else if ("--location".equals(args[i]) && i + 1 < args.length) location = args[++i];
            else if ("--interval".equals(args[i]) && i + 1 < args.length) interval = Double.parseDouble(args[++i]);
        }
        SensorSimulator s = new SensorSimulator(host, port, type, id, location, interval);
        Runtime.getRuntime().addShutdownHook(new Thread(s::stop));
        s.run();
    }
}

package org.eclipse.californium.examples.dos;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.IOException;
import java.net.SocketTimeoutException;
import java.util.concurrent.TimeUnit;

import javax.net.ssl.SSLContext;

import org.apache.hc.core5.http.ClassicHttpRequest;
import org.apache.hc.core5.http.ClassicHttpResponse;
import org.apache.hc.core5.http.ConnectionClosedException;
import org.apache.hc.core5.http.ContentType;
import org.apache.hc.core5.http.ExceptionListener;
import org.apache.hc.core5.http.HttpConnection;
import org.apache.hc.core5.http.HttpException;
import org.apache.hc.core5.http.impl.bootstrap.HttpServer;
import org.apache.hc.core5.http.impl.bootstrap.ServerBootstrap;
import org.apache.hc.core5.http.io.HttpRequestHandler;
import org.apache.hc.core5.http.io.SocketConfig;
import org.apache.hc.core5.http.io.entity.BasicHttpEntity;
import org.apache.hc.core5.http.protocol.HttpContext;
import org.apache.hc.core5.io.CloseMode;
import org.apache.hc.core5.ssl.SSLContexts;
import org.apache.hc.core5.util.TimeValue;

// Source https://github.com/apache/httpcomponents-core/blob/5.1.x/httpcore5/src/test/java/org/apache/hc/core5/http/examples/ClassicFileServerExample.java
public class DevHTTPSServer {

  private static final int port = 8443;
  private static final String certsHome = "/Users/amirfarhat/workplace/research/dos-californium/demo-certs/src/main/resources/";

  private static HttpServer createHTTPSServer() {
    try {
      // Key store
      final File keyStoreFile = new File(certsHome + "keyStore.jks");
      final char[] keyStorePassword = "endPass".toCharArray();

      // Trust store
      final File trustStoreFile = new File(certsHome + "trustStore.jks");
      final char[] trustStorePassword = "rootPass".toCharArray();

      // Initialize SSL context
      final SSLContext sslContext = 
        SSLContexts
        .custom()
        .loadKeyMaterial(keyStoreFile, keyStorePassword, keyStorePassword)
        .loadTrustMaterial(trustStoreFile, trustStorePassword)
        .build();

      final SocketConfig socketConfig = 
        SocketConfig.custom()
        .setSoTimeout(15, TimeUnit.SECONDS)
        .setTcpNoDelay(true)
        .build();

      return 
        ServerBootstrap.bootstrap()
        .setListenerPort(port)
        .setSocketConfig(socketConfig)
        .setSslContext(sslContext)
        .setExceptionListener(new ExceptionListener() {
          @Override
          public void onError(final Exception ex) {
            ex.printStackTrace();
          }

          @Override
          public void onError(final HttpConnection conn, final Exception ex) {
            if (ex instanceof SocketTimeoutException) {
              System.err.println("Connection timed out");
            } else if (ex instanceof ConnectionClosedException) {
              System.err.println(ex.getMessage());
            } else {
              ex.printStackTrace();
            }
          }
        })
        .register("*", new HttpRequestHandler() {
          @Override
          public void handle(ClassicHttpRequest request, ClassicHttpResponse response, HttpContext context) throws HttpException, IOException {
            response.setCode(200);
            response.setEntity(new BasicHttpEntity(
              new ByteArrayInputStream("Hello from dev https server!".getBytes()),
              ContentType.TEXT_PLAIN)
            );
          }
        })
        .create();
    } catch (Exception e) {
      throw new RuntimeException(e);
    }
  }
  
  public static void main(String[] args) throws IOException, InterruptedException {
    final HttpServer server = createHTTPSServer();
    server.start();
    Runtime.getRuntime().addShutdownHook(new Thread() {
      @Override
      public void run() {
        server.close(CloseMode.GRACEFUL);
      }
    });
    System.out.println("Listening on port " + port);

    server.awaitTermination(TimeValue.MAX_VALUE);
  }
}
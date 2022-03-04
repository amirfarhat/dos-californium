package org.eclipse.californium.examples.dos;

import java.io.IOException;
import java.security.KeyManagementException;
import java.security.KeyStoreException;
import java.security.NoSuchAlgorithmException;
import java.security.cert.CertificateException;
import java.security.cert.X509Certificate;

import javax.net.ssl.SSLContext;

import org.apache.hc.client5.http.classic.methods.HttpGet;
import org.apache.hc.client5.http.impl.classic.CloseableHttpClient;
import org.apache.hc.client5.http.impl.classic.CloseableHttpResponse;
import org.apache.hc.client5.http.impl.classic.HttpClients;
import org.apache.hc.client5.http.impl.io.PoolingHttpClientConnectionManagerBuilder;
import org.apache.hc.client5.http.io.HttpClientConnectionManager;
import org.apache.hc.client5.http.ssl.SSLConnectionSocketFactory;
import org.apache.hc.client5.http.ssl.SSLConnectionSocketFactoryBuilder;
import org.apache.hc.core5.http.ParseException;
import org.apache.hc.core5.http.io.entity.EntityUtils;
import org.apache.hc.core5.http.ssl.TLS;
import org.apache.hc.core5.ssl.SSLContexts;
import org.apache.hc.core5.ssl.TrustStrategy;

// Source: https://github.com/apache/httpcomponents-client/blob/5.1.x/httpclient5/src/test/java/org/apache/hc/client5/http/examples/ClientCustomSSL.java
public class DevHTTPSClient {

  private static CloseableHttpClient createHTTPSClient() throws KeyManagementException, NoSuchAlgorithmException, KeyStoreException {
    // Trust everyone
    final SSLContext sslcontext = 
      SSLContexts
      .custom()
      .loadTrustMaterial(new TrustStrategy() {
        @Override
        public boolean isTrusted(X509Certificate[] chain, String authType) throws CertificateException {
          return true;
        }
      }).build();
    
    // Allow TLSv1.2 protocol only
    final SSLConnectionSocketFactory sslSocketFactory = 
      SSLConnectionSocketFactoryBuilder
      .create()
      .setSslContext(sslcontext)
      .setTlsVersions(TLS.V_1_2)
      .build();

    // Instruct connection manager to use the SSL factory above
    final HttpClientConnectionManager cm = 
      PoolingHttpClientConnectionManagerBuilder.create()
      .setSSLSocketFactory(sslSocketFactory)
      .build();
    
    // Build client
    return
      HttpClients.custom()
      .setConnectionManager(cm)
      .build();
  }

  private static void printResponse(CloseableHttpResponse response) throws ParseException, IOException {
    if (response == null) {
      return;
    }
    System.out.println("----------------------------------------");
    System.out.println(response.getCode() + " " + response.getReasonPhrase());
    System.out.println(EntityUtils.toString(response.getEntity()));
    System.out.println("----------------------------------------");
  }

  public static void main(String[] args) {
    // Parse command line arguments
    if (args.length != 1) {
      System.err.println("Expected target URL as argument");
    }
    final String url = args[0];

    // Execute GET request using fresh client
    try {
      final CloseableHttpClient httpClient = createHTTPSClient();
      CloseableHttpResponse response = httpClient.execute(new HttpGet(url));
      printResponse(response);
    } catch (Exception e) {
      throw new RuntimeException(e);
    }
  } 
}
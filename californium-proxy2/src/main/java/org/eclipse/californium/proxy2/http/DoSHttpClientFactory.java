package org.eclipse.californium.proxy2.http;

import java.io.IOException;
import java.io.InterruptedIOException;
import java.net.ConnectException;
import java.net.UnknownHostException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

import javax.net.ssl.SSLException;

import org.apache.hc.client5.http.ConnectTimeoutException;
import org.apache.hc.client5.http.config.RequestConfig;
import org.apache.hc.client5.http.impl.DefaultConnectionKeepAliveStrategy;
import org.apache.hc.client5.http.impl.DefaultHttpRequestRetryStrategy;
import org.apache.hc.client5.http.impl.async.CloseableHttpAsyncClient;
import org.apache.hc.client5.http.impl.async.HttpAsyncClientBuilder;
import org.apache.hc.client5.http.impl.nio.PoolingAsyncClientConnectionManager;
import org.apache.hc.client5.http.impl.nio.PoolingAsyncClientConnectionManagerBuilder;
import org.apache.hc.core5.http.ConnectionClosedException;
import org.apache.hc.core5.http.ConnectionReuseStrategy;
import org.apache.hc.core5.http.HttpRequest;
import org.apache.hc.core5.http.HttpResponse;
import org.apache.hc.core5.http.protocol.HttpContext;
import org.apache.hc.core5.http.protocol.RequestConnControl;
import org.apache.hc.core5.http.protocol.RequestDate;
import org.apache.hc.core5.http.protocol.RequestExpectContinue;
import org.apache.hc.core5.http.protocol.RequestTargetHost;
import org.apache.hc.core5.http.protocol.RequestUserAgent;
import org.apache.hc.core5.http2.HttpVersionPolicy;
import org.apache.hc.core5.pool.PoolConcurrencyPolicy;
import org.apache.hc.core5.pool.PoolReusePolicy;
import org.apache.hc.core5.reactor.IOReactorConfig;
import org.apache.hc.core5.util.TimeValue;
import org.apache.hc.core5.util.Timeout;
import org.eclipse.californium.elements.config.Configuration;
import org.eclipse.californium.proxy2.config.DoSConfig;
import org.eclipse.californium.proxy2.config.Proxy2Config;

/**
 * Factory for egress async HTTP clients that are optimized for DoS attacks.
 * 
 * @author amirf@mit.edu
 */
public class DoSHttpClientFactory {

  private static AtomicReference<Configuration> config = new AtomicReference<Configuration>();

	private DoSHttpClientFactory() {
	}

	/**
	 * Set the configuration for the http client.
	 * 
	 * @param config configuration
	 * @return previous configuration, or {@code null}, if not available
	 * @since 3.0 (changed return type and parameter to Configuration)
	 */
	public static Configuration setNetworkConfig(Configuration config) {
		return DoSHttpClientFactory.config.getAndSet(config);
	}

	/**
	 * Get the configuration for the http client.
	 * 
	 * @return configuration for the http client
	 * @since 3.0 (changed return type to Configuration)
	 */
	public static Configuration getNetworkConfig() {
		Configuration config = DoSHttpClientFactory.config.get();
		if (config == null) {
			DoSHttpClientFactory.config.compareAndSet(null, Configuration.getStandard());
			config = DoSHttpClientFactory.config.get();
		}
		return config;
	}

  /**
   * Create the pooled asynchronous http client, optimized for DoS performance.
   * 
   * @return configured and ready-to-use asynchronous http client
   */
  public static CloseableHttpAsyncClient createCustomClient() {
    // Get config of the http client factory
    Configuration config = getNetworkConfig();

    final TimeValue requestRetryInterval = TimeValue.ofSeconds(config.get(DoSConfig.REQUEST_RETRY_INTERVAL, TimeUnit.SECONDS));
    final int maxRequestRetries = config.get(DoSConfig.MAX_RETRIES);
    final boolean reuseConnections = config.get(DoSConfig.REUSE_CONNECTIONS);
    final TimeValue keepAliveDuration = TimeValue.ofSeconds(config.get(DoSConfig.KEEP_ALIVE_DURATION, TimeUnit.SECONDS));

		final CloseableHttpAsyncClient client = HttpAsyncClientBuilder
      .create()
      .disableCookieManagement()
      .setVersionPolicy(HttpVersionPolicy.NEGOTIATE)

      // Configure http requests
      .setDefaultRequestConfig(createCustomRequestConfig(config))

      // Configure the manager of http connections
      .setConnectionManager(createPoolingConnManager(config))

      // Configure IO reactor (mostly socket setup)
      .setIOReactorConfig(createCustomIOReactorConfig(config))

      // Request interceptors to add first
      .addRequestInterceptorFirst(new RequestConnControl())
      .addRequestInterceptorFirst(new RequestDate())
      .addRequestInterceptorFirst(new RequestExpectContinue())
      .addRequestInterceptorFirst(new RequestTargetHost())
      .addRequestInterceptorFirst(new RequestUserAgent())

      // Reuse strategy
      .setConnectionReuseStrategy(new ConnectionReuseStrategy() {
        @Override
        public boolean keepAlive(HttpRequest request, HttpResponse response, HttpContext context) {
          return reuseConnections;
        }
      })
      
      // Keep-alive strategy
      .setKeepAliveStrategy(new DefaultConnectionKeepAliveStrategy() {
        @Override
        public TimeValue getKeepAliveDuration(HttpResponse response, HttpContext context) {
          TimeValue keepAlive = super.getKeepAliveDuration(response, context);
          if (keepAlive == null || keepAlive.getDuration() < 0) {
            // Keep connections alive if a keep-alive value
            // has not be explicitly set by the server
            keepAlive = keepAliveDuration;
          }
          return keepAlive;
        }
      })

      // Retry strategy
      .setRetryStrategy(new DefaultHttpRequestRetryStrategy() {
        private boolean checkRetry(int execCount) {
          return execCount <= maxRequestRetries;
        }
        private boolean checkRetry(IOException exception, int execCount) {
          // Want to retry on certain exceptions for fixed number of retries
          final boolean exceptionIsSupported = (exception instanceof ConnectTimeoutException)
                                              || (exception instanceof InterruptedIOException)
                                              || (exception instanceof UnknownHostException)
                                              || (exception instanceof ConnectException)
                                              || (exception instanceof ConnectionClosedException)
                                              || (exception instanceof SSLException);
          final boolean canStillRetry = checkRetry(execCount);
          return exceptionIsSupported && canStillRetry;
        }

        @Override
        public TimeValue getRetryInterval(HttpResponse response, int execCount, HttpContext context) {
          return requestRetryInterval;
        }

        @Override
        public boolean retryRequest(HttpResponse response, int execCount, HttpContext context) {
          return checkRetry(execCount);
        }

        @Override
        public boolean retryRequest(HttpRequest request, IOException exception, int execCount, HttpContext context) {
          return checkRetry(exception, execCount);
        }
      })
      .build();

		client.start();
		return client;
  }

	/**
	 * Create the http request-config.
	 * 
	 * @param config configuration for the http client
	 * @return http request-config
	 * @since 3.0 (changed parameter to Configuration)
	 */
	private static RequestConfig createCustomRequestConfig(Configuration config) {
		// Source: https://hc.apache.org/httpcomponents-client-5.1.x/current/httpclient5/apidocs/org/apache/hc/client5/http/config/RequestConfig.Builder.html

    final TimeValue keepAliveDuration = TimeValue.ofSeconds(config.get(DoSConfig.KEEP_ALIVE_DURATION, TimeUnit.SECONDS));
    final long requestTimeoutSec = config.get(DoSConfig.REQUEST_TIMEOUT, TimeUnit.SECONDS);

    final long connectTimeoutMillis = config.get(Proxy2Config.HTTP_CONNECT_TIMEOUT, TimeUnit.MILLISECONDS);

		return RequestConfig
      .custom()
      .setConnectionKeepAlive(keepAliveDuration)
      .setConnectionRequestTimeout(Timeout.ofSeconds(requestTimeoutSec))
      .setConnectTimeout(Timeout.ofMilliseconds(connectTimeoutMillis))
      .build();
	}

	/**
	 * Create pooling connection Manager.
	 * 
	 * @param config configuration for the http client
	 * @return pooling connection Manager
	 * @since 3.0 (changed parameter to Configuration)
	 */
	private static PoolingAsyncClientConnectionManager createPoolingConnManager(Configuration config) {
		// Source: https://hc.apache.org/httpcomponents-client-5.1.x/current/httpclient5/apidocs/org/apache/hc/client5/http/impl/nio/PoolingAsyncClientConnectionManagerBuilder.html

    final TimeValue keepAliveDuration = TimeValue.ofSeconds(config.get(DoSConfig.KEEP_ALIVE_DURATION, TimeUnit.SECONDS));
    final int numProxyConnections = config.get(DoSConfig.NUM_PROXY_CONNECTIONS);

    return PoolingAsyncClientConnectionManagerBuilder
      .create()
      .setConnectionTimeToLive(keepAliveDuration)
      .setConnPoolPolicy(PoolReusePolicy.FIFO)
      // setDnsResolver(DnsResolver dnsResolver)
      .setMaxConnTotal(numProxyConnections)
      .setMaxConnPerRoute(numProxyConnections)
      .setPoolConcurrencyPolicy(PoolConcurrencyPolicy.STRICT)
      // setSchemePortResolver(SchemePortResolver schemePortResolver)
      // setTlsStrategy(org.apache.hc.core5.http.nio.ssl.TlsStrategy tlsStrategy)
      // setValidateAfterInactivity(org.apache.hc.core5.util.TimeValue validateAfterInactivity) <-- default is 0ms
      // useSystemProperties()
      .build();
	}

  private static IOReactorConfig createCustomIOReactorConfig(Configuration config) {
		// Source: https://hc.apache.org/httpcomponents-core-5.1.x/current/httpcore5/apidocs/org/apache/hc/core5/reactor/IOReactorConfig.Builder.html
		//
		// setDefaultMaxIOThreadCount(int defaultMaxIOThreadCount)
		// setIoThreadCount(int ioThreadCount)
		// Some socket options like:
		// 		setRcvBufSize(int rcvBufSize)
		// 		setSndBufSize(int sndBufSize)
		// 		setSoKeepAlive(boolean soKeepAlive)
		// 		setSoLinger(TimeValue soLinger)
		// 		setSoReuseAddress(boolean soReuseAddress)
		// 		setSoTimeout(Timeout soTimeout)
		//		setTcpNoDelay(boolean tcpNoDelay)
		//		setTrafficClass(int trafficClass)

    final long connectionIdleSecs = config.get(Proxy2Config.HTTP_CONNECTION_IDLE_TIMEOUT, TimeUnit.SECONDS);
		return IOReactorConfig
						.custom()
						.setSoTimeout(Timeout.ofSeconds(connectionIdleSecs))
						.build();
	}
} 
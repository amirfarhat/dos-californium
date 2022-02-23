package org.eclipse.californium.proxy2.http;

import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

import org.apache.hc.client5.http.config.RequestConfig;
import org.apache.hc.client5.http.impl.DefaultConnectionKeepAliveStrategy;
import org.apache.hc.client5.http.impl.DefaultHttpRequestRetryStrategy;
import org.apache.hc.client5.http.impl.async.CloseableHttpAsyncClient;
import org.apache.hc.client5.http.impl.async.HttpAsyncClientBuilder;
import org.apache.hc.client5.http.impl.nio.PoolingAsyncClientConnectionManager;
import org.apache.hc.client5.http.impl.nio.PoolingAsyncClientConnectionManagerBuilder;
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
		return DoSHttpClientFactory.config.get();
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
          // In the case where the response from the recipient contains a keep-alive field,
          // we want to use that value
          TimeValue keepAlive = super.getKeepAliveDuration(response, context);
          
          if (keepAlive == null || keepAlive.getDuration() < 0) {
            // But in the case where a keep-alive is not specified, we set our own
            keepAlive = keepAliveDuration;
          }
          
          return keepAlive;
        }
      })

      // Retry strategy
      .setRetryStrategy(new DefaultHttpRequestRetryStrategy(maxRequestRetries, requestRetryInterval))

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

    final long keepAliveDurationSec = config.get(DoSConfig.KEEP_ALIVE_DURATION, TimeUnit.SECONDS);
    final long requestTimeoutSec = config.get(DoSConfig.REQUEST_TIMEOUT, TimeUnit.SECONDS);

		return RequestConfig
      .custom()
      .setConnectionRequestTimeout(Timeout.ofSeconds(requestTimeoutSec))
      .setConnectTimeout(Timeout.ofSeconds(keepAliveDurationSec))
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

    final boolean reuseConnections = config.get(DoSConfig.REUSE_CONNECTIONS);
    final int numProxyConnections = config.get(DoSConfig.NUM_PROXY_CONNECTIONS);

    // If we re-use connections, the keep-alive time should be virtually infinite, whereas
    // if we do NOT re-use connections, connections should be kept alive for the configured time.
    final TimeValue keepAliveDuration = 
      reuseConnections 
        ? null
        : TimeValue.ofSeconds(config.get(DoSConfig.KEEP_ALIVE_DURATION, TimeUnit.SECONDS));

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

    final long keepAliveDurationSec = config.get(DoSConfig.KEEP_ALIVE_DURATION, TimeUnit.SECONDS);
		return IOReactorConfig
						.custom()
						.setSoTimeout(Timeout.ofSeconds(keepAliveDurationSec))
						.build();
	}
} 
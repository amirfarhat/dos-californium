package org.eclipse.californium.examples.dos;

import java.io.File;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.security.GeneralSecurityException;
import java.util.concurrent.TimeUnit;

import org.eclipse.californium.core.CoapServer;
import org.eclipse.californium.core.config.CoapConfig;
import org.eclipse.californium.core.network.CoapEndpoint;
import org.eclipse.californium.elements.config.Configuration;
import org.eclipse.californium.elements.config.Configuration.DefinitionsProvider;
import org.eclipse.californium.elements.config.IntegerDefinition;
import org.eclipse.californium.elements.config.SystemConfig;
import org.eclipse.californium.elements.config.TcpConfig;
import org.eclipse.californium.elements.config.UdpConfig;
import org.eclipse.californium.examples.util.SecureEndpointPool;
import org.eclipse.californium.proxy2.config.DoSConfig;
import org.eclipse.californium.proxy2.config.Proxy2Config;
import org.eclipse.californium.proxy2.http.Coap2HttpTranslator;
import org.eclipse.californium.proxy2.http.DoSHttpClientFactory;
import org.eclipse.californium.proxy2.resources.DoSProxyHttpClientResource;
import org.eclipse.californium.proxy2.resources.ForwardProxyMessageDeliverer;
import org.eclipse.californium.proxy2.resources.ProxyCoapResource;
import org.eclipse.californium.scandium.DTLSConnector;
import org.eclipse.californium.scandium.MdcConnectionListener;
import org.eclipse.californium.scandium.config.DtlsConfig;
import org.eclipse.californium.scandium.config.DtlsConnectorConfig;

public class DoSOptimizedDTLSProxy {

	private static final File CONFIG_FILE = new File("CaliforniumSecureProxy3.properties");
	private static final String CONFIG_HEADER = "Californium CoAP Properties file for Secure Example Proxy";
	private static final int DEFAULT_MAX_RESOURCE_SIZE = 8192;
	private static final int DEFAULT_BLOCK_SIZE = 1024;

	public static final IntegerDefinition OUTGOING_MAX_ACTIVE_PEERS = new IntegerDefinition("OUTGOING_MAX_ACTIVE_PEERS",
			"Maximum number of outgoing peers per endpoint.", 32, 8);

	public static final IntegerDefinition OUTGOING_DTLS_MAX_CONNECTIONS = new IntegerDefinition(
			"OUTGOING_DTLS_MAX_CONNECTIONS", "Maximum number of outgoing DTLS connections per endpoint.", 32, 8);

	public static final IntegerDefinition MAX_CONNECTION_POOL_SIZE = new IntegerDefinition("MAX_CONNECTION_POOL_SIZE",
			"Maximum size of connection pool.", 1000, 32);

	public static final IntegerDefinition INIT_CONNECTION_POOL_SIZE = new IntegerDefinition("INIT_CONNECTION_POOL_SIZE",
			"Initial size of connection pool.", 250, 16);

	static {
		DoSConfig.register();
    CoapConfig.register();
		UdpConfig.register();
		DtlsConfig.register();
		TcpConfig.register();
		Proxy2Config.register();
	}

	/**
	 * Special configuration defaults handler.
	 */
	private static final DefinitionsProvider DEFAULTS = new DefinitionsProvider() {

		@Override
		public void applyDefinitions(Configuration config) {
			config.set(CoapConfig.MAX_ACTIVE_PEERS, 20000);
			config.set(CoapConfig.MAX_RESOURCE_BODY_SIZE, DEFAULT_MAX_RESOURCE_SIZE);
			config.set(CoapConfig.MAX_MESSAGE_SIZE, DEFAULT_BLOCK_SIZE);
			config.set(CoapConfig.PREFERRED_BLOCK_SIZE, DEFAULT_BLOCK_SIZE);
			config.set(CoapConfig.MAX_PEER_INACTIVITY_PERIOD, 24, TimeUnit.HOURS);
			config.set(Proxy2Config.HTTP_CONNECTION_IDLE_TIMEOUT, 10, TimeUnit.SECONDS);
			config.set(Proxy2Config.HTTP_CONNECT_TIMEOUT, 15, TimeUnit.SECONDS);
			config.set(Proxy2Config.HTTPS_HANDSHAKE_TIMEOUT, 30, TimeUnit.SECONDS);
			config.set(UdpConfig.UDP_RECEIVE_BUFFER_SIZE, 8192);
			config.set(UdpConfig.UDP_SEND_BUFFER_SIZE, 8192);
			config.set(DtlsConfig.DTLS_RECEIVE_BUFFER_SIZE, 8192);
			config.set(DtlsConfig.DTLS_SEND_BUFFER_SIZE, 8192);
			config.set(DtlsConfig.DTLS_RECEIVER_THREAD_COUNT, 1);
			config.set(DtlsConfig.DTLS_CONNECTOR_THREAD_COUNT, 1);
			config.set(SystemConfig.HEALTH_STATUS_INTERVAL, 60, TimeUnit.SECONDS);
			config.set(OUTGOING_MAX_ACTIVE_PEERS, 32);
			config.set(OUTGOING_DTLS_MAX_CONNECTIONS, 32);
			config.set(MAX_CONNECTION_POOL_SIZE, 1000);
			config.set(INIT_CONNECTION_POOL_SIZE, 250);
		}
	};

	private static final String COAPS2HTTP = "coaps2http";

	public DoSOptimizedDTLSProxy(Configuration config) throws IOException, GeneralSecurityException {
		// Pass configuration to the http client pool
    DoSHttpClientFactory.setNetworkConfig(config);
		
    // Set up main config
    Configuration outgoingConfig = new Configuration(config);
    outgoingConfig.set(CoapConfig.MAX_ACTIVE_PEERS, config.get(OUTGOING_MAX_ACTIVE_PEERS));
		outgoingConfig.set(DtlsConfig.DTLS_MAX_CONNECTIONS, config.get(OUTGOING_DTLS_MAX_CONNECTIONS));
		outgoingConfig.set(DtlsConfig.DTLS_RECEIVER_THREAD_COUNT, 1);
		outgoingConfig.set(DtlsConfig.DTLS_CONNECTOR_THREAD_COUNT, 1);
    final int coapsPort = config.get(CoapConfig.COAP_SECURE_PORT);

    // Set up coap to http forwarding
    boolean visible = false; // Resource visible to clients via discovery
    boolean accept = false; // Only respond to coap client after receiving http response
    Coap2HttpTranslator translator = new Coap2HttpTranslator();
		ProxyCoapResource coapsToHttpResource = new DoSProxyHttpClientResource(COAPS2HTTP, visible, accept, translator);
    ForwardProxyMessageDeliverer forwardProxyMessageDeliverer = new ForwardProxyMessageDeliverer(coapsToHttpResource);

    // Configure DTLS connector
    final DtlsConnectorConfig dtlsConnectorConfig = SecureEndpointPool
      .setupServer(outgoingConfig)
      .setAddress(new InetSocketAddress(coapsPort))
      .setConnectionListener(new MdcConnectionListener())
      .build();
    final DTLSConnector dtlsConnector = new DTLSConnector(dtlsConnectorConfig);

    // Configure coap endpoint
    final CoapEndpoint coapEndpoint = new CoapEndpoint.Builder()
				.setConfiguration(outgoingConfig)
				.setConnector(dtlsConnector)
        .build();
    coapEndpoint.setMessageDeliverer(forwardProxyMessageDeliverer);

    // Finally, set up coap server
    final CoapServer proxyCoapsServer = new CoapServer();
    proxyCoapsServer.addEndpoint(coapEndpoint);
    proxyCoapsServer.setMessageDeliverer(forwardProxyMessageDeliverer);
    proxyCoapsServer.start();
		System.out.println("** CoAPs Proxy at: coap://localhost:" + coapsPort);
    System.out.println("Heap size in MB: " + Runtime.getRuntime().maxMemory() / (1000*1000));
	}

	public static void main(String args[]) throws IOException, GeneralSecurityException {
		Configuration proxyConfig = Configuration.createWithFile(CONFIG_FILE, CONFIG_HEADER, DEFAULTS);
		new DoSOptimizedDTLSProxy(proxyConfig);
	}
}
package org.eclipse.californium.examples.dos;

import java.io.File;
import java.io.IOException;
import java.util.concurrent.TimeUnit;

import org.eclipse.californium.core.CoapServer;
import org.eclipse.californium.core.config.CoapConfig;
import org.eclipse.californium.elements.config.Configuration;
import org.eclipse.californium.elements.config.SystemConfig;
import org.eclipse.californium.elements.config.TcpConfig;
import org.eclipse.californium.elements.config.UdpConfig;
import org.eclipse.californium.elements.config.Configuration.DefinitionsProvider;
import org.eclipse.californium.proxy2.config.DoSConfig;
import org.eclipse.californium.proxy2.config.Proxy2Config;
import org.eclipse.californium.proxy2.http.Coap2HttpTranslator;
import org.eclipse.californium.proxy2.http.DoSHttpClientFactory;
import org.eclipse.californium.proxy2.resources.DoSProxyHttpClientResource;
import org.eclipse.californium.proxy2.resources.ForwardProxyMessageDeliverer;
import org.eclipse.californium.proxy2.resources.ProxyCoapResource;

public class DoSOptimizedForwardingProxy {
	
	// Configuration file name.
	private static final File CONFIG_FILE = new File("DoSProxy.properties");

	// Header for configuration file.
	private static final String CONFIG_HEADER = "Californium CoAP Properties file for DoS-Optimized Forwarding Proxy";

	// Default size in bytes to use for UDP buffers.
	private static final int DEFAULT_UDP_BUFFER_SIZE = 8192;

	static {
		CoapConfig.register();
		UdpConfig.register();
		TcpConfig.register();
		Proxy2Config.register();
		DoSConfig.register();
	}

  /**
	 * Special configuration defaults handler.
	 */
	private static final DefinitionsProvider DEFAULTS = new DefinitionsProvider() {
    @Override
		public void applyDefinitions(Configuration config) {
			// We expect the proxy to communicate with a single server, one attacker,
			// and many clients. So we choose a small two digit number to accommodate.
      config.set(CoapConfig.MAX_ACTIVE_PEERS, 15);

			// Choose in-memory map of messages *per peer* for de-duplication
			config.set(CoapConfig.DEDUPLICATOR, CoapConfig.DEDUPLICATOR_PEERS_MARK_AND_SWEEP);
			
			// Peers should become inactive according to worst-case experiment recovery time
			config.set(CoapConfig.MAX_PEER_INACTIVITY_PERIOD, 10, TimeUnit.MINUTES);
			
			config.set(UdpConfig.UDP_RECEIVE_BUFFER_SIZE, DEFAULT_UDP_BUFFER_SIZE);
			config.set(UdpConfig.UDP_SEND_BUFFER_SIZE, DEFAULT_UDP_BUFFER_SIZE);

			// Enable periodic checking of health status
			config.set(SystemConfig.HEALTH_STATUS_INTERVAL, 60, TimeUnit.SECONDS);
    }
  };

  private static final String COAP2HTTP = "coap2http";

  private CoapServer coapProxyServer;

  public DoSOptimizedForwardingProxy(Configuration config) throws IOException {
    // Pass configuration to the http client pool
    DoSHttpClientFactory.setNetworkConfig(config);

    // Create coap server at the ingress of the dos proxy
    int port = config.get(CoapConfig.COAP_PORT);
    coapProxyServer = new CoapServer(config, port);

    // Determine whether this resource is visible to clients. The proxy will work if this is false, so
    // it is left as false
    boolean visible = false;

    // Do not return a respponse to the coap client before receiving an http response
    boolean accept = false;

    // Translates coap2http outgoing and http2coap incoming
    Coap2HttpTranslator translator = new Coap2HttpTranslator();

    // Tie all the configurations together
    ProxyCoapResource coap2http = new DoSProxyHttpClientResource(COAP2HTTP, visible, accept, translator);
    ForwardProxyMessageDeliverer proxyMessageDeliverer = new ForwardProxyMessageDeliverer(coap2http);

    // Launch the coap server on proxy ingress
    coapProxyServer.setMessageDeliverer(proxyMessageDeliverer);
    coapProxyServer.start();

    System.out.println("** CoAP Proxy at: coap://localhost:" + port);
    System.out.println("Heap size in MB: " + Runtime.getRuntime().maxMemory() / (1000*1000));
  }

  public static void main(String args[]) throws IOException {
    // Create and/or read proxy configuration file
    Configuration proxyConfig = Configuration.createWithFile(CONFIG_FILE, CONFIG_HEADER, DEFAULTS);

    // Create proxy and run
		DoSOptimizedForwardingProxy proxy = new DoSOptimizedForwardingProxy(proxyConfig);
		System.out.println(DoSOptimizedForwardingProxy.class.getSimpleName() + " started.");
  }
}
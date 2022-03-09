package org.eclipse.californium.examples.dos;

import java.io.IOException;
import java.security.GeneralSecurityException;

import org.eclipse.californium.core.CoapClient;
import org.eclipse.californium.core.network.CoapEndpoint;
import org.eclipse.californium.elements.config.Configuration;
import org.eclipse.californium.examples.util.SecureEndpointPool;
import org.eclipse.californium.scandium.DTLSConnector;
import org.eclipse.californium.scandium.config.DtlsConnectorConfig;

public class DoSUtil {

  public static final int MAX_MID = 64999;

  public static CoapClient makeCoapClient(boolean schemeIsCoap, Configuration configuration) throws IOException, GeneralSecurityException {
		CoapClient client = new CoapClient();
		if (schemeIsCoap) {
			System.out.println("Make CoAP client");
		} else {
			System.out.println("Make CoAPs client");

			// Configure DTLS connector
			final DtlsConnectorConfig dtlsConnectorConfig = SecureEndpointPool
      	.setupClient(configuration)
      	.build();
			final DTLSConnector dtlsConnector = new DTLSConnector(dtlsConnectorConfig);

			// Configure coap endpoint
			final CoapEndpoint coapEndpoint = new CoapEndpoint.Builder()
					.setConfiguration(configuration)
					.setConnector(dtlsConnector)
					.build();
					
			client.setEndpoint(coapEndpoint);
		}

		return client;
	}
}

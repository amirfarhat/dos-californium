package org.eclipse.californium.examples.dos;

import java.io.File;
import java.io.IOException;
import java.sql.Timestamp;
import java.util.concurrent.atomic.AtomicInteger;

import org.eclipse.californium.core.CoapClient;
import org.eclipse.californium.core.CoapResponse;
import org.eclipse.californium.core.coap.Request;
import org.eclipse.californium.core.config.CoapConfig;
import org.eclipse.californium.core.network.RandomTokenGenerator;
import org.eclipse.californium.core.network.TokenGenerator.Scope;
import org.eclipse.californium.elements.config.Configuration;
import org.eclipse.californium.elements.config.TcpConfig;
import org.eclipse.californium.elements.config.UdpConfig;
import org.eclipse.californium.elements.exception.ConnectorException;
import org.eclipse.californium.proxy2.config.DoSConfig;
import org.eclipse.californium.proxy2.config.Proxy2Config;

public class DoSSynchronousCoapClient {

	private static final int MAX_MID = 64999;
	private static final boolean VERBOSE = true;

  private static final AtomicInteger reqCount = new AtomicInteger(0);

	static {
		CoapConfig.register();
		UdpConfig.register();
		TcpConfig.register();
		Proxy2Config.register();
		DoSConfig.register();
	}

	private static CoapResponse request(CoapClient client, Request request) {
		dPrint("Send: " + reqCount.incrementAndGet());
		try {
			CoapResponse response = client.advanced(request);
			dPrint("Recv: " + reqCount.get());
			return response;
		} catch (ConnectorException | IOException e) {
			throw new RuntimeException(e);
		}
	}

	private static void dPrint(Object obj) {
		if (VERBOSE) {
			Timestamp timestamp = new Timestamp(System.currentTimeMillis());
			System.out.println(String.format(
				"%s -- %s",
				timestamp,
				obj
			));
		}
	}
  public static void main(String[] args) {
    // Configure parameters from input args
		if (args.length != 2 && args.length != 3) {
			System.out.println("Args [proxy uri] [dest uri] [OPTIONAL num_messages int]");
			System.exit(1);
		}
		String proxyUri = args[0];
		String destinationUri = args[1];
		int num_messages;
		if (args.length == 3) {
			num_messages = Integer.parseInt(args[2]);
		} else {
			num_messages = Integer.MAX_VALUE; // basically infinite
		}

		// Create client
		final Configuration config = Configuration.getStandard();
		RandomTokenGenerator tokenGenerator = new RandomTokenGenerator(config);
		CoapClient client = new CoapClient();
		
		// Prepare client configuration
		client.useCONs();
		// Builder reliabilityParams = ReliabilityLayerParameters.builder();

		String midTok, destinationUriWithMidTok;
		Request request;

		for (int i = 1; i <= num_messages; i++) {
			// Use new GET request
			request = Request.newGet();
			request.setURI(proxyUri);
			
			// Need to mod by MAX_MID to avoid multicase MID range
			request.setMID(i % MAX_MID);
			request.setToken(tokenGenerator.createToken(Scope.LONG_TERM));
			
			// Set mid_tok combination for after-the-fact analysis
			midTok = request.getMID() + "_" + request.getTokenString();
			destinationUriWithMidTok = destinationUri + "/" + midTok;
			request.getOptions().setProxyUri(destinationUriWithMidTok);

			// TODO client reliability parameters here
			// request.setReliabilityLayerParameters();

			request(client, request);
		}
  }
}
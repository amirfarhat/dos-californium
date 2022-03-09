package org.eclipse.californium.examples.dos;

import java.io.File;
import java.io.IOException;
import java.security.GeneralSecurityException;
import java.sql.Timestamp;
import java.util.concurrent.atomic.AtomicInteger;

import org.eclipse.californium.core.CoapClient;
import org.eclipse.californium.core.CoapResponse;
import org.eclipse.californium.core.coap.Request;
import org.eclipse.californium.core.config.CoapConfig;
import org.eclipse.californium.core.network.RandomTokenGenerator;
import org.eclipse.californium.core.network.TokenGenerator.Scope;
import org.eclipse.californium.core.network.stack.ReliabilityLayerParameters;
import org.eclipse.californium.elements.config.Configuration;
import org.eclipse.californium.elements.config.TcpConfig;
import org.eclipse.californium.elements.config.UdpConfig;
import org.eclipse.californium.elements.exception.ConnectorException;
import org.eclipse.californium.proxy2.config.DoSConfig;
import org.eclipse.californium.proxy2.config.Proxy2Config;
import org.eclipse.californium.scandium.config.DtlsConfig;

public class DoSSynchronousCoapClient {

	private static final File CLIENT_TIMEOUT_CONFIG_FILE = new File("DoSClient.properties");

	private static final boolean VERBOSE = true;

  private static final AtomicInteger reqCount = new AtomicInteger(0);

	static {
		CoapConfig.register();
		UdpConfig.register();
		TcpConfig.register();
		Proxy2Config.register();
		DoSConfig.register();
		DtlsConfig.register();
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

  public static void main(String[] args) throws IOException, GeneralSecurityException {
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

		// Determine if this client uses DTLS or not
		boolean schemeIsCoap;
		if (proxyUri.startsWith("coaps")) {
			schemeIsCoap = false;
		} else if (proxyUri.startsWith("coap")) {
			schemeIsCoap = true;
		} else {
			throw new RuntimeException("Unrecognized scheme " + proxyUri);
		}
		
		// Prepare client configuration
		final Configuration timeoutConfig = new Configuration();
		timeoutConfig.load(CLIENT_TIMEOUT_CONFIG_FILE);
		final ReliabilityLayerParameters reliabilityParams = ReliabilityLayerParameters
			.builder()
			.applyConfig(timeoutConfig)
			.build();

		// Create client
		final CoapClient client = DoSUtil.makeCoapClient(schemeIsCoap, timeoutConfig);
		client.useCONs();

		RandomTokenGenerator tokenGenerator = new RandomTokenGenerator(Configuration.getStandard());
		String midTok, destinationUriWithMidTok;
		Request request;

		for (int i = 1; i <= num_messages; i++) {
			// Use new GET request
			request = Request.newGet();
			request.setURI(proxyUri);
			
			// Need to mod by MAX_MID to avoid multicase MID range
			request.setMID(i % DoSUtil.MAX_MID);
			request.setToken(tokenGenerator.createToken(Scope.LONG_TERM));
			
			// Set mid_tok combination for after-the-fact analysis
			midTok = request.getMID() + "_" + request.getTokenString();
			destinationUriWithMidTok = destinationUri + "/" + midTok;
			request.getOptions().setProxyUri(destinationUriWithMidTok);

			// Update reliability parameters
			request.setReliabilityLayerParameters(reliabilityParams);

			request(client, request);
		}
  }
}
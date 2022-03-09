/*******************************************************************************
 * Copyright (c) 2020 Bosch.IO GmbH and others.
 * 
 * All rights reserved. This program and the accompanying materials
 * are made available under the terms of the Eclipse Public License v2.0
 * and Eclipse Distribution License v1.0 which accompany this distribution.
 * 
 * The Eclipse Public License is available at
 *    http://www.eclipse.org/legal/epl-v20.html
 * and the Eclipse Distribution License is available at
 *    http://www.eclipse.org/org/documents/edl-v10.html.
 * 
 * Contributors:
 *    Bosch.IO GmbH - initial implementation
 ******************************************************************************/
package org.eclipse.californium.examples;

import java.io.IOException;
import java.security.GeneralSecurityException;
import java.util.Arrays;

import org.eclipse.californium.elements.exception.ConnectorException;
import org.eclipse.californium.examples.basic.BasicForwardingProxy2;
import org.eclipse.californium.examples.dos.DoSSynchronousCoapClient;
import org.eclipse.californium.examples.dos.DevHTTPSClient;
import org.eclipse.californium.examples.dos.DevHTTPSServer;
import org.eclipse.californium.examples.dos.DoSDTLSAttacker;
import org.eclipse.californium.examples.dos.DoSOptimizedDTLSProxy;
import org.eclipse.californium.examples.dos.DoSOptimizedForwardingProxy;

/**
 * Main starter class for jar execution.
 */
public class Proxy2 {

	private static final String CROSS_PROXY = ExampleCrossProxy2.class.getSimpleName();
	private static final String SECURE_PROXY = ExampleSecureProxy2.class.getSimpleName();
	private static final String COAP_CLIENT = ExampleProxy2CoapClient.class.getSimpleName();
	private static final String HTTP_CLIENT = ExampleProxy2HttpClient.class.getSimpleName();
	private static final String COAP_SERVER = ExampleCoapServer.class.getSimpleName();
	private static final String HTTP_SERVER = ExampleHttpServer.class.getSimpleName();
	private static final String SECURE_COAP_CLIENT = ExampleSecureProxy2CoapClient.class.getSimpleName();

	private static final String BASIC_FORWARDING_PROXY = BasicForwardingProxy2.class.getSimpleName();
	private static final String DOS_FORWARDING_PROXY = DoSOptimizedForwardingProxy.class.getSimpleName();
	private static final String DOS_SYNC_PROXY_COAP_CLIENT = DoSSynchronousCoapClient.class.getSimpleName();
	private static final String DOS_DTLS_PROXY = DoSOptimizedDTLSProxy.class.getSimpleName();
	private static final String DEV_HTTPS_SERVER = DevHTTPSServer.class.getSimpleName();
	private static final String DEV_HTTPS_CLIENT = DevHTTPSClient.class.getSimpleName();
	private static final String DOS_DTLS_ATTACKER = DoSDTLSAttacker.class.getSimpleName();

	public static void main(String[] args)
			throws IOException, ConnectorException, InterruptedException, GeneralSecurityException {
		String start = args.length > 0 ? args[0] : null;
		if (start != null) {
			String[] args2 = Arrays.copyOfRange(args, 1, args.length);
			if (CROSS_PROXY.equals(start)) {
				ExampleCrossProxy2.main(args2);
				return;
			} else if (SECURE_PROXY.equals(start)) {
				ExampleSecureProxy2.main(args2);
				return;
			} else if (SECURE_COAP_CLIENT.equals(start)) {
				ExampleSecureProxy2CoapClient.main(args2);
				return;
			} else if (COAP_CLIENT.equals(start)) {
				ExampleProxy2CoapClient.main(args2);
				return;
			} else if (HTTP_CLIENT.equals(start)) {
				ExampleProxy2HttpClient.main(args2);
				return;
			} else if (COAP_SERVER.equals(start)) {
				ExampleCoapServer.main(args2);
				return;
			} else if (HTTP_SERVER.equals(start)) {
				ExampleHttpServer.main(args2);
				return;
			} else if (BASIC_FORWARDING_PROXY.equals(start)) {
				BasicForwardingProxy2.main(args2);
				return;
			} else if (DOS_FORWARDING_PROXY.equals(start)) {
				DoSOptimizedForwardingProxy.main(args2);
				return;
			} else if (DOS_SYNC_PROXY_COAP_CLIENT.equals(start)) {
				DoSSynchronousCoapClient.main(args2);
				return;
			} else if (DOS_DTLS_PROXY.equals(start)) {
				DoSOptimizedDTLSProxy.main(args2);
				return;
			} else if (DEV_HTTPS_SERVER.equals(start)) {
				DevHTTPSServer.main(args2);
				return;
			} else if (DEV_HTTPS_CLIENT.equals(start)) {
				DevHTTPSClient.main(args2);
				return;
			} else if (DOS_DTLS_ATTACKER.equals(start)) {
				DoSDTLSAttacker.main(args2);
				return;
			}
		}
		System.out.println("\nCalifornium (Cf) Proxy2-Starter");
		System.out.println("(c) 2020, Bosch.IO GmbH and others");
		System.out.println();
		System.out.println(
				"Usage: " + Proxy2.class.getSimpleName() + " (" + CROSS_PROXY + "|" + SECURE_PROXY + "|" + COAP_CLIENT
						+ "|" + SECURE_COAP_CLIENT + "|" + HTTP_CLIENT + "|" + COAP_SERVER + "|" + HTTP_SERVER
						+ "|" + BASIC_FORWARDING_PROXY + "|" + DOS_FORWARDING_PROXY + "|" + DOS_SYNC_PROXY_COAP_CLIENT 
						+ "|" + DOS_DTLS_PROXY + "|" + DEV_HTTPS_SERVER + "|" + DEV_HTTPS_CLIENT + "|" + DOS_DTLS_ATTACKER
						+ ")");
		if (start != null) {
			System.out.println("   '" + start + "' is not supported!");
		}
		System.exit(-1);
	}
}

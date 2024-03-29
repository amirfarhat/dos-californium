/*******************************************************************************
 * Copyright (c) 2022 Bosch IO GmbH and others.
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
 *    Bosch.IO GmbH - initial implementation.
 ******************************************************************************/
package org.eclipse.californium.interoperability.test.mbedtls;

import static org.eclipse.californium.interoperability.test.ProcessUtil.TIMEOUT_MILLIS;
import static org.eclipse.californium.interoperability.test.mbedtls.MbedTlsProcessUtil.AuthenticationMode.CHAIN;
import static org.junit.Assert.assertTrue;
import static org.junit.Assume.assumeNotNull;

import java.io.IOException;
import java.net.InetAddress;
import java.net.InetSocketAddress;

import org.eclipse.californium.elements.config.Configuration;
import org.eclipse.californium.elements.rule.TestNameLoggerRule;
import org.eclipse.californium.interoperability.test.ConnectorUtil;
import org.eclipse.californium.interoperability.test.ProcessUtil.ProcessResult;
import org.eclipse.californium.interoperability.test.ScandiumUtil;
import org.eclipse.californium.interoperability.test.ShutdownUtil;
import org.eclipse.californium.scandium.config.DtlsConfig;
import org.eclipse.californium.scandium.config.DtlsConnectorConfig;
import org.eclipse.californium.scandium.dtls.cipher.CipherSuite;
import org.eclipse.californium.scandium.dtls.cipher.CipherSuite.CertificateKeyAlgorithm;
import org.junit.After;
import org.junit.AfterClass;
import org.junit.BeforeClass;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.Parameterized;
import org.junit.runners.Parameterized.Parameter;
import org.junit.runners.Parameterized.Parameters;

/**
 * Test for interoperability with Mbed TLS client.
 * 
 * Test several different cipher suites.
 * 
 * @see MbedTlsUtil
 * @since 3.3
 */
@RunWith(Parameterized.class)
public class MbedTlsClientInteroperabilityTest {

	@Rule
	public TestNameLoggerRule name = new TestNameLoggerRule();

	private static final InetSocketAddress BIND = new InetSocketAddress(InetAddress.getLoopbackAddress(),
			ScandiumUtil.PORT);
	private static final String DESTINATION = "127.0.0.1";

	private static MbedTlsProcessUtil processUtil;
	private static ScandiumUtil scandiumUtil;

	@BeforeClass
	public static void init() throws IOException, InterruptedException {
		processUtil = new MbedTlsProcessUtil();
		ProcessResult result = processUtil.getMbedTlsVersion(TIMEOUT_MILLIS);
		assumeNotNull(result);
		scandiumUtil = new ScandiumUtil(false);
	}

	@AfterClass
	public static void shutdown() throws InterruptedException {
		ShutdownUtil.shutdown(scandiumUtil, processUtil);
	}

	@Parameter
	public CipherSuite cipherSuite;

	/**
	 * @return List of cipher suites.
	 */
	@Parameters(name = "{0}")
	public static Iterable<CipherSuite> cipherSuiteParams() {
		return MbedTlsUtil.getSupportedTestCipherSuites();
	}

	@After
	public void stop() throws InterruptedException {
		ShutdownUtil.shutdown(scandiumUtil, processUtil);
	}

	/**
	 * Establish a "connection" and send a message to the server and back to the
	 * client.
	 */
	@Test
	public void testMbedTlsClient() throws Exception {
		processUtil.setTag("mbedtls-client, " + cipherSuite.name());
		if (cipherSuite.getCertificateKeyAlgorithm() == CertificateKeyAlgorithm.RSA) {
			scandiumUtil.loadCredentials(ConnectorUtil.SERVER_RSA_NAME);
		}
		scandiumUtil.start(BIND, null, cipherSuite);

		String cipher = processUtil.startupClient(DESTINATION, ScandiumUtil.PORT, CHAIN, cipherSuite);
		assertTrue(processUtil.waitConsole("Ciphersuite is " + cipher, TIMEOUT_MILLIS));

		String message = "Hello Scandium!";

		// Mbed TLS client sends a HTTP GET request, even in DTLS mode
		scandiumUtil.assertContainsReceivedData("GET / HTTP/1.0", TIMEOUT_MILLIS);
		scandiumUtil.response("ACK-" + message, TIMEOUT_MILLIS);

		assertTrue("mbedTls is missing ACK!", processUtil.waitConsole("ACK-" + message, TIMEOUT_MILLIS));

		processUtil.stop(TIMEOUT_MILLIS);
	}

	/**
	 * Establish a "connection" and send a message to the server and back to the
	 * client.
	 */
	@Test
	public void testMbedTlsClientMultiFragments() throws Exception {
		processUtil.setTag("mbedtls-client, multifragments per record, " + cipherSuite.name());
		DtlsConnectorConfig.Builder builder = DtlsConnectorConfig.builder(new Configuration())
				.set(DtlsConfig.DTLS_USE_MULTI_HANDSHAKE_MESSAGE_RECORDS, true);
		if (cipherSuite.getCertificateKeyAlgorithm() == CertificateKeyAlgorithm.RSA) {
			scandiumUtil.loadCredentials(ConnectorUtil.SERVER_RSA_NAME);
		}
		scandiumUtil.start(BIND, builder, null, cipherSuite);

		String cipher = processUtil.startupClient(DESTINATION, ScandiumUtil.PORT, CHAIN, cipherSuite);
		assertTrue(processUtil.waitConsole("Ciphersuite is " + cipher, TIMEOUT_MILLIS));

		String message = "Hello Scandium!";

		// Mbed TLS client sends a HTTP GET request, even in DTLS mode
		scandiumUtil.assertContainsReceivedData("GET / HTTP/1.0", TIMEOUT_MILLIS);
		scandiumUtil.response("ACK-" + message, TIMEOUT_MILLIS);

		assertTrue(processUtil.waitConsole("ACK-" + message, TIMEOUT_MILLIS));

		processUtil.stop(TIMEOUT_MILLIS);
	}
}

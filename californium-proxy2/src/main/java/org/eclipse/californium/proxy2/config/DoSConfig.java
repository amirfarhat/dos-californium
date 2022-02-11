package org.eclipse.californium.proxy2.config;

import java.util.concurrent.TimeUnit;

import org.eclipse.californium.elements.config.BooleanDefinition;
import org.eclipse.californium.elements.config.Configuration;
import org.eclipse.californium.elements.config.IntegerDefinition;
import org.eclipse.californium.elements.config.SystemConfig;
import org.eclipse.californium.elements.config.TimeDefinition;
import org.eclipse.californium.elements.config.Configuration.ModuleDefinitionsProvider;

/**
 * Houser of configuration parameters that are strongly tied to DoS attacks.
 * 
 * @author amirf@mit.edu
 */
public final class DoSConfig {

	public static final String MODULE = "DOS.";

	/* Proxy Egress Connections */
	public static final int DEFAULT_NUM_PROXY_CONNECTIONS = 25;
	public static final IntegerDefinition NUM_PROXY_CONNECTIONS = new IntegerDefinition(
		MODULE + "NUM_PROXY_CONNECTIONS",
		"The number of egress connections to open at the proxy",
		DEFAULT_NUM_PROXY_CONNECTIONS,
		0
	);
	
	/* Reuse Connections */
	public static final boolean DEFAULT_REUSE_CONNECTIONS = true;
	public static final BooleanDefinition REUSE_CONNECTIONS = new BooleanDefinition(
		MODULE + "REUSE_CONNECTIONS",
		"Flag to set whether the connections that are allocated should be kept alive",
		DEFAULT_REUSE_CONNECTIONS
	);

	/* Keep Alive Duration. Behavior defined only when `REUSE_CONNECTIONS` is `true` */
	public static final long DEFAULT_KEEP_ALIVE_DURATION = 5;
	public static final TimeDefinition KEEP_ALIVE_DURATION = new TimeDefinition(
		MODULE + "KEEP_ALIVE_DURATION", 
		"The duration to keep egress TCP connections alive for before proxy-side termination",
		DEFAULT_KEEP_ALIVE_DURATION,
		TimeUnit.SECONDS
	);

	/* Retry Interval */
	public static final long DEFAULT_REQUEST_RETRY_INTERVAL = 1;
	public static final TimeDefinition REQUEST_RETRY_INTERVAL = new TimeDefinition(
		MODULE + "REQUEST_RETRY_INTERVAL", 
		"The time to wait before egress HTTP requests are retried",
		DEFAULT_REQUEST_RETRY_INTERVAL,
		TimeUnit.SECONDS
	);

	/* Request Retries */
	public static final int DEFAULT_MAX_RETRIES = 2;
	public static final IntegerDefinition MAX_RETRIES = new IntegerDefinition(
		MODULE + "MAX_RETRIES",
		"The amount of times to retry a egress HTTP request that has failed",
		DEFAULT_MAX_RETRIES,
		0
	);

	/* Request Timeout */
	public static final int DEFAULT_REQUEST_TIMEOUT = 5;
	public static final TimeDefinition REQUEST_TIMEOUT = new TimeDefinition(
		MODULE + "REQUEST_TIMEOUT",
		"The amount of times to retry an egress HTTP request that has failed",
		DEFAULT_REQUEST_TIMEOUT,
		TimeUnit.SECONDS
	);

	public static final ModuleDefinitionsProvider DEFINITIONS = new ModuleDefinitionsProvider() {

		@Override
		public String getModule() {
			return MODULE;
		}

		@Override
		public void applyDefinitions(Configuration config) {
			config.set(NUM_PROXY_CONNECTIONS, DEFAULT_NUM_PROXY_CONNECTIONS);
			config.set(REUSE_CONNECTIONS, DEFAULT_REUSE_CONNECTIONS);
			config.set(KEEP_ALIVE_DURATION, DEFAULT_KEEP_ALIVE_DURATION, TimeUnit.SECONDS);
			config.set(REQUEST_RETRY_INTERVAL, DEFAULT_REQUEST_RETRY_INTERVAL, TimeUnit.SECONDS);
			config.set(MAX_RETRIES, DEFAULT_MAX_RETRIES);
			config.set(REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT, TimeUnit.SECONDS);
		}
	};

	static {
		Configuration.addDefaultModule(DEFINITIONS);
	}

	public static void register() {
		SystemConfig.register();
	}
}
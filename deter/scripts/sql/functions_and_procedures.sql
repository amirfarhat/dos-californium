
-- 
-- EXPERIMENT
-- 
CREATE OR REPLACE FUNCTION insert_into_experiment(
	exp_name text, 
	attacker_rate text,
	server_connections int,
	max_keep_alive_requests int,
	num_clients int,
	num_trials int,
	origin_server_duration int,
	attacker_duration int,
	receiver_duration int,
	proxy_duration int,
	client_duration int,
	attacker_start_lag_duration int,
	topology text,
	num_proxy_connections int,
	request_timeout text,
	max_retries int,
	keep_alive_duration text,
	request_retry_interval text,
	reuse_connections boolean,
	run_proxy_with_dtls boolean,
	run_proxy_with_https boolean,
	run_attacker boolean
) RETURNS VOID AS $$

INSERT INTO experiment 
VALUES (exp_name, attacker_rate, server_connections, max_keep_alive_requests, 
			  num_clients, num_trials, origin_server_duration, attacker_duration, 
				receiver_duration, proxy_duration, client_duration, attacker_start_lag_duration, topology, 
				num_proxy_connections, request_timeout, max_retries, keep_alive_duration, request_retry_interval, reuse_connections,
				run_proxy_with_dtls, run_proxy_with_https, run_attacker)
ON CONFLICT 
DO NOTHING
;

$$ LANGUAGE SQL;



-- 
-- NODE
-- 
CREATE OR REPLACE FUNCTION insert_into_node(
	in_node_name text, 
	in_hardware_type text,
	in_operating_system text
) RETURNS int AS $$

-- Insert new node if not already present

DECLARE
	found_id node.node_id%TYPE := 0;
BEGIN
	SELECT n.node_id INTO found_id
		FROM node AS n 
	WHERE n.node_name = in_node_name 
		AND n.hardware_type = in_hardware_type 
		AND n.operating_system = in_operating_system
	LIMIT 1;
	
	IF found_id <= 0 OR found_id ISNULL THEN
		INSERT INTO node (node_name, hardware_type, operating_system)
		VALUES (in_node_name, in_hardware_type, in_operating_system)
		RETURNING node_id
		INTO found_id;
	END IF;
	
	RETURN found_id;
END;

$$ LANGUAGE plpgsql;


-- 
-- COAP_MESSAGE_CONTENT
-- 
CREATE OR REPLACE FUNCTION insert_into_coap(
	in_coap_type text, 
	in_coap_code text,
	in_coap_retransmitted boolean
) RETURNS int AS $$

-- Insert new coap message if not already present

DECLARE
	found_id coap_message.cmci%TYPE := 0;
BEGIN
	SELECT coap.cmci INTO found_id
		FROM coap_message AS coap
	WHERE coap.coap_type = in_coap_type 
		AND coap.coap_code = in_coap_code
		AND coap.coap_retransmitted = in_coap_retransmitted
	LIMIT 1;
	
	IF found_id <= 0 OR found_id ISNULL THEN
		INSERT INTO coap_message 
			(coap_type, coap_code, coap_retransmitted) 
		VALUES
			(in_coap_type, in_coap_code, in_coap_retransmitted)
		RETURNING cmci
		INTO found_id;	
	END IF;
	
	RETURN found_id;
END;

$$ LANGUAGE plpgsql;



-- 
-- HTTP_MESSAGE_CONTENT
-- 
CREATE OR REPLACE FUNCTION insert_into_http(
	in_http_request boolean,
	in_http_request_method text,
	in_http_response_code int
) RETURNS int AS $$

-- Insert new http message if not already present

DECLARE
	found_id http_message.hmci%TYPE := 0;
BEGIN
	SELECT hmci INTO found_id
		FROM http_message AS h
	WHERE h.http_request = in_http_request
		AND COALESCE(h.http_request_method, '') = COALESCE(in_http_request_method, '')
		AND COALESCE(h.http_response_code, -1) = COALESCE(in_http_response_code, -1)
	LIMIT 1;
	
	IF found_id <= 0 OR found_id ISNULL THEN
		INSERT INTO http_message
			(http_request, http_request_method, http_response_code)
		VALUES
			(in_http_request, in_http_request_method, in_http_response_code)
		RETURNING hmci
		INTO found_id;	
	END IF;
	
	RETURN found_id;
END;

$$ LANGUAGE plpgsql;




-- 
-- DEPLOYED_NODE
-- 
CREATE OR REPLACE FUNCTION insert_into_deployed_node(
	in_exp_id text, 
	in_node_id int
) RETURNS int AS $$

-- Insert new deployed node if not already present

DECLARE
	found_id deployed_node.dnid%TYPE := 0;
BEGIN
	SELECT d.dnid INTO found_id
		FROM deployed_node AS d
	WHERE d.exp_id = in_exp_id 
		AND d.node_id = in_node_id
	LIMIT 1;
	
	IF found_id <= 0 OR found_id ISNULL THEN
		INSERT INTO deployed_node 
			(exp_id, node_id) 
		VALUES
			(in_exp_id, in_node_id) 
		RETURNING dnid
		INTO found_id;	
	END IF;
	
	RETURN found_id;
END;

$$ LANGUAGE plpgsql;

--
-- MESSAGE FOR COAP
-- 
CREATE OR REPLACE FUNCTION insert_into_message_coap(
	in_size_bytes int,
	in_src_id int,
	in_dst_id int,
	in_coap_message int
) RETURNS int AS $$

-- Insert new message if not already present

DECLARE
	found_id message.message_id%TYPE := 0;
BEGIN
	SELECT m.message_id INTO found_id
		FROM message AS m
	WHERE m.size_bytes = in_size_bytes
		AND m.src_id = in_src_id
		AND m.dst_id = in_dst_id
		AND m.coap_message = in_coap_message
	LIMIT 1;
	
	IF found_id <= 0 OR found_id ISNULL THEN
		INSERT INTO message 
			(size_bytes, src_id, dst_id, coap_message)
		VALUES
			(in_size_bytes, in_src_id, in_dst_id, in_coap_message)
		RETURNING message_id
		INTO found_id;
	END IF;
	
	RETURN found_id;
END;

$$ LANGUAGE plpgsql;


--
-- MESSAGE FOR HTTP
-- 
CREATE OR REPLACE FUNCTION insert_into_message_http(
	in_size_bytes int,
	in_src_id int,
	in_dst_id int,
	in_http_message int
) RETURNS int AS $$

-- Insert new message if not already present

DECLARE
	found_id message.message_id%TYPE := 0;
BEGIN
	SELECT m.message_id INTO found_id
		FROM message AS m
	WHERE  m.size_bytes = in_size_bytes
		AND m.src_id = in_src_id
		AND m.dst_id = in_dst_id
		AND m.http_message = in_http_message
	LIMIT 1;
	
	IF found_id <= 0 OR found_id ISNULL THEN
		INSERT INTO message 
			(size_bytes, src_id, dst_id, http_message)
		VALUES
			(in_size_bytes, in_src_id, in_dst_id, in_http_message)
		RETURNING message_id
		INTO found_id;
	END IF;
	
	RETURN found_id;
END;

$$ LANGUAGE plpgsql;



-- 
-- EVENT: DEPRECATED
-- 
CREATE OR REPLACE FUNCTION insert_into_event(
	in_observer_id int,
	in_message_id int,
	in_observe_timestamp decimal,
	in_trial int
) RETURNS VOID AS $$

-- Insert new event if not exists

DECLARE
	found_trial event.trial%TYPE := 0;
BEGIN
	SELECT e.trial INTO found_trial
		FROM event AS e
	WHERE e.observer_id = in_observer_id
		AND e.message_id = in_message_id
		AND e.observe_timestamp = in_observe_timestamp
		AND e.trial = in_trial
	LIMIT 1;
	
	IF found_trial = 0 OR found_trial ISNULL THEN
		INSERT INTO 
			event 
		VALUES
			(in_observer_id, in_message_id, in_observe_timestamp, in_trial);
	END IF;
END;

$$ LANGUAGE plpgsql;


-- 
-- ADD COAP PROCEDURE : DEPRECATED
-- 
CREATE OR REPLACE PROCEDURE add_coap_message(
	in_coap_type text, 
	in_coap_code text,
	in_coap_retransmitted boolean,
	in_size_bytes int,
	in_src_id int,
	in_dst_id int,
	in_observer_id int,
	in_observe_timestamp decimal,
	in_trial int
) AS $$

DECLARE
	coap_content_id int;
	coap_message_id int;
BEGIN
	SELECT insert_into_coap(in_coap_type, in_coap_code, in_coap_retransmitted) INTO coap_content_id;

	SELECT insert_into_message_coap(in_size_bytes, in_src_id, in_dst_id, coap_content_id) INTO coap_message_id;
  
	PERFORM insert_into_event(in_observer_id, coap_message_id, in_observe_timestamp, in_trial);
END;

$$ LANGUAGE plpgsql;
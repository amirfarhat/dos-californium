-- 
-- 
-- Helper to get the table sizes taken up on disk for the current database
-- 
-- 

-- Sum event table partition sizes
WITH event_size AS (
SELECT
    'event' AS table_full_name,
    SUM(pg_total_relation_size('"' || table_schema || '"."' || table_name || '"')) AS size
FROM information_schema.tables
WHERE table_schema = 'public' AND table_name LIKE 'event_with_observer%'
GROUP BY table_schema

-- Sum node_metric table partition sizes
), node_metric_size AS (
SELECT
    'node_metric' AS table_full_name,
    SUM(pg_total_relation_size('"' || table_schema || '"."' || table_name || '"')) AS size
FROM information_schema.tables
WHERE table_schema = 'public' AND table_name LIKE 'node_metric_with_observer%'
GROUP BY table_schema

-- Sum all table sizes without partitions
), all_table_sizes AS (
SELECT
    table_name AS table_full_name,
    pg_total_relation_size('"' || table_schema || '"."' || table_name || '"') AS size
FROM information_schema.tables
WHERE table_schema = 'public' AND table_name not LIKE '%with_observer_id%'
ORDER BY
    pg_total_relation_size('"' || table_schema || '"."' || table_name || '"') DESC

-- Sum all table sizes as human-readable
), final_all_table_sizes AS (
SELECT 
	t_all.table_full_name,
	pg_size_pretty(
		(COALESCE(t_all.size, 0)) 
		+ (COALESCE(t_event.size, 0))
		+ (COALESCE(t_node_metric.size, 0))
	) AS size
FROM all_table_sizes t_all
LEFT OUTER JOIN event_size t_event ON t_event.table_full_name = t_all.table_full_name
LEFT OUTER JOIN node_metric_size t_node_metric ON t_node_metric.table_full_name = t_all.table_full_name

-- 
-- 
-- Helper to get the number of table rows for each table in the current database
-- 
-- 

-- Sum event table partition rows
), event_stats AS (
SELECT 
	'event' AS relname,
	SUM(n_live_tup) AS n_live_tup
FROM pg_stat_user_tables
WHERE
	relname LIKE '%event_with_observer_id%'

-- Sum node_metric table partition rows
), node_metric_stats AS (
SELECT 
	'node_metric' AS relname,
	SUM(n_live_tup) AS n_live_tup
FROM pg_stat_user_tables
WHERE
	relname LIKE '%node_metric_with_observer_id%'

-- Sum all table rows without partitions
), all_table_stats AS (
SELECT 
	relname, n_live_tup
FROM pg_stat_user_tables
WHERE 
	relname LIKE '%experiment%'
	OR relname = 'experiment'
	OR relname = 'deployed_node'
	OR relname = 'node'
	OR relname = 'event'
	OR relname = 'node_metric'
	OR relname = 'message'
	OR relname = 'coap_message'
	OR relname = 'http_message'

-- Sum all table rows
), final_all_table_stats AS (
SELECT 
	t_all.relname AS table_full_name, 
	(COALESCE(t_all.n_live_tup, 0)
	 + COALESCE(t_event.n_live_tup, 0)
	 + COALESCE(t_node_metric.n_live_tup, 0)) AS num_rows
FROM all_table_stats t_all
LEFT JOIN event_stats t_event ON t_event.relname = t_all.relname
LEFT JOIN node_metric_stats t_node_metric ON t_node_metric.relname = t_all.relname
ORDER BY num_rows DESC
)

-- 
-- 
-- Helper to combine table stats and sizes
-- 
-- 

SELECT
	final_all_table_stats.table_full_name,
	final_all_table_sizes.size,
	final_all_table_stats.num_rows
FROM
	final_all_table_stats 
	JOIN final_all_table_sizes 
	ON final_all_table_stats.table_full_name = final_all_table_sizes.table_full_name
ORDER BY 
	num_rows DESC
-- TMDB analysis queries
-- Each query starts with a "-- name:" line and a "-- question:" line.
-- src/run_queries.py runs them all and saves results to reports/query_results/.
-- Unknown money: the `movies` table keeps TMDB's raw budget/revenue, where 0 means "unknown".
-- Queries that use money read the view `v_movie_summary`, which turns unknown values into NULL
-- (so AVG/SUM ignore them) and derives profit and ROI. See notebooks/01_eda.ipynb, section 2.
-- ROI queries also require budget >= $1M (see config.MIN_BUDGET_FOR_ROI).

-- name: q01_dataset_overview
-- question: How big is the dataset and how complete are the financials?
SELECT COUNT(*)                                   AS films,
       MIN(release_year)                          AS first_year,
       MAX(release_year)                          AS last_year,
       SUM(budget IS NULL)                        AS budget_unknown,
       SUM(revenue IS NULL)                       AS revenue_unknown,
       SUM(roi IS NOT NULL)                       AS films_with_both,
       ROUND(100.0 * SUM(roi IS NOT NULL) / COUNT(*), 1) AS pct_with_both,
       ROUND(AVG(runtime), 1)                     AS avg_runtime_min,
       ROUND(AVG(vote_average), 2)                AS avg_rating,
       ROUND(SUM(revenue) / 1e9, 1)               AS total_revenue_bn
FROM v_movie_summary;

-- name: q02_genre_performance
-- question: Which genres earn the most, rate best and return the most per dollar?
SELECT g.genre_name,
       COUNT(*)                                   AS films,
       ROUND(AVG(m.vote_average), 2)              AS avg_rating,
       ROUND(AVG(m.revenue) / 1e6, 1)             AS avg_revenue_m,
       ROUND(AVG(m.budget) / 1e6, 1)              AS avg_budget_m,
       ROUND(SUM(m.revenue) * 1.0 / SUM(m.budget), 2) AS pooled_roi
FROM movie_genres mg
JOIN genres g USING (genre_id)
JOIN v_movie_summary m USING (movie_id)
WHERE m.budget >= 1000000 AND m.revenue IS NOT NULL
GROUP BY g.genre_name
HAVING COUNT(*) >= 20
ORDER BY avg_revenue_m DESC;

-- name: q03_top_grossing_films
-- question: What are the 15 highest-grossing films, and who directed them?
SELECT title, release_year,
       ROUND(revenue / 1e6, 0) AS revenue_m,
       ROUND(budget / 1e6, 0)  AS budget_m,
       directors, genres
FROM v_movie_summary
WHERE revenue IS NOT NULL
ORDER BY revenue DESC
LIMIT 15;

-- name: q04_best_roi_films
-- question: Which films returned the most per dollar of budget (budget >= $1M)?
SELECT title, release_year,
       ROUND(budget / 1e6, 1)  AS budget_m,
       ROUND(revenue / 1e6, 1) AS revenue_m,
       ROUND(roi, 1)           AS roi_multiple,
       genres
FROM v_movie_summary
WHERE budget >= 1000000 AND revenue IS NOT NULL
ORDER BY roi DESC
LIMIT 15;

-- name: q05_trends_by_decade
-- question: How have budgets, revenues, runtimes and ratings changed by decade?
SELECT decade,
       COUNT(*)                         AS films,
       ROUND(AVG(budget) / 1e6, 1)      AS avg_budget_m,
       ROUND(AVG(revenue) / 1e6, 1)     AS avg_revenue_m,
       ROUND(AVG(runtime), 1)           AS avg_runtime,
       ROUND(AVG(vote_average), 2)      AS avg_rating
FROM v_movie_summary
GROUP BY decade
ORDER BY decade;

-- name: q06_top_directors_by_revenue
-- question: Which directors (3+ films) have the highest total box office?
SELECT p.person_name                    AS director,
       COUNT(DISTINCT m.movie_id)       AS films,
       ROUND(SUM(m.revenue) / 1e9, 2)   AS total_revenue_bn,
       ROUND(AVG(m.vote_average), 2)    AS avg_rating
FROM crew_credits c
JOIN jobs j   USING (job_id)
JOIN people p USING (person_id)
JOIN v_movie_summary m USING (movie_id)
WHERE j.job = 'Director'
GROUP BY p.person_id
HAVING COUNT(DISTINCT m.movie_id) >= 3
ORDER BY total_revenue_bn DESC
LIMIT 15;

-- name: q07_most_consistent_directors
-- question: Which directors (5+ films) are rated highest on average, and how consistent are they?
WITH d AS (
    SELECT p.person_id, p.person_name, m.vote_average
    FROM crew_credits c
    JOIN jobs j   USING (job_id)
    JOIN people p USING (person_id)
    JOIN v_movie_summary m USING (movie_id)
    WHERE j.job = 'Director'
)
SELECT person_name                              AS director,
       COUNT(*)                                 AS films,
       ROUND(AVG(vote_average), 2)              AS avg_rating,
       ROUND(MIN(vote_average), 2)              AS worst,
       ROUND(MAX(vote_average), 2)              AS best,
       ROUND(MAX(vote_average) - MIN(vote_average), 2) AS spread
FROM d
GROUP BY person_id
HAVING COUNT(*) >= 5
ORDER BY avg_rating DESC
LIMIT 15;

-- name: q08_most_prolific_actors
-- question: Which actors appear most often in top-billed (top 5) roles, and how do their films do?
SELECT p.person_name                   AS actor,
       COUNT(*)                        AS lead_roles,
       ROUND(AVG(m.vote_average), 2)   AS avg_rating,
       ROUND(SUM(m.revenue) / 1e9, 2)  AS total_revenue_bn
FROM cast_credits c
JOIN people p USING (person_id)
JOIN v_movie_summary m USING (movie_id)
WHERE c.cast_order < 5
GROUP BY p.person_id
ORDER BY lead_roles DESC, total_revenue_bn DESC
LIMIT 15;

-- name: q09_actor_director_pairs
-- question: Which actor-director partnerships recur most often?
SELECT d.person_name AS director,
       a.person_name AS actor,
       COUNT(*)      AS films_together,
       ROUND(AVG(m.vote_average), 2) AS avg_rating
FROM crew_credits cr
JOIN jobs j          ON j.job_id = cr.job_id AND j.job = 'Director'
JOIN cast_credits ca ON ca.movie_id = cr.movie_id AND ca.cast_order < 5
JOIN people d        ON d.person_id = cr.person_id
JOIN people a        ON a.person_id = ca.person_id
JOIN movies m        ON m.movie_id = cr.movie_id
WHERE cr.person_id <> ca.person_id
GROUP BY cr.person_id, ca.person_id
HAVING COUNT(*) >= 4
ORDER BY films_together DESC, avg_rating DESC
LIMIT 15;

-- name: q10_top_keywords
-- question: Which story keywords are most common, and which genre do they belong to most?
WITH kw AS (
    SELECT k.keyword_id, k.keyword_name, COUNT(*) AS films
    FROM movie_keywords mk JOIN keywords k USING (keyword_id)
    GROUP BY k.keyword_id
),
kw_genre AS (
    SELECT mk.keyword_id, g.genre_name, COUNT(*) AS n,
           ROW_NUMBER() OVER (PARTITION BY mk.keyword_id ORDER BY COUNT(*) DESC) AS rk
    FROM movie_keywords mk
    JOIN movie_genres mg USING (movie_id)
    JOIN genres g USING (genre_id)
    GROUP BY mk.keyword_id, g.genre_name
)
SELECT kw.keyword_name, kw.films, kg.genre_name AS most_common_genre
FROM kw JOIN kw_genre kg ON kg.keyword_id = kw.keyword_id AND kg.rk = 1
ORDER BY kw.films DESC
LIMIT 20;

-- name: q11_keyword_lift
-- question: Which keywords (15+ films) are associated with the highest average revenue?
SELECT k.keyword_name,
       COUNT(*)                        AS films,
       ROUND(AVG(m.revenue) / 1e6, 0)  AS avg_revenue_m,
       ROUND(AVG(m.vote_average), 2)   AS avg_rating
FROM movie_keywords mk
JOIN keywords k USING (keyword_id)
JOIN v_movie_summary m USING (movie_id)
WHERE m.revenue IS NOT NULL
GROUP BY k.keyword_id
HAVING COUNT(*) >= 15
ORDER BY avg_revenue_m DESC
LIMIT 15;

-- name: q12_budget_tiers
-- question: Do bigger budgets mean better returns and ratings?
WITH tiered AS (
    SELECT *,
           CASE WHEN budget <  20000000 THEN '1. Under $20M'
                WHEN budget <  60000000 THEN '2. $20M-$60M'
                WHEN budget < 120000000 THEN '3. $60M-$120M'
                ELSE                         '4. $120M+' END AS budget_tier
    FROM v_movie_summary
    WHERE budget >= 1000000 AND revenue IS NOT NULL
)
SELECT budget_tier,
       COUNT(*)                                       AS films,
       ROUND(AVG(roi), 2)                             AS mean_roi,
       ROUND(100.0 * SUM(revenue < budget) / COUNT(*), 1) AS pct_lost_money,
       ROUND(AVG(vote_average), 2)                    AS avg_rating
FROM tiered
GROUP BY budget_tier
ORDER BY budget_tier;

-- name: q13_release_month
-- question: Which release months bring the highest average revenue?
SELECT release_month,
       COUNT(*)                       AS films,
       ROUND(AVG(revenue) / 1e6, 1)   AS avg_revenue_m,
       ROUND(AVG(vote_average), 2)    AS avg_rating
FROM v_movie_summary
WHERE revenue IS NOT NULL
GROUP BY release_month
ORDER BY release_month;

-- name: q14_best_film_per_year
-- question: What was the best-rated film each year since 2000 (min 1,000 votes)?
WITH ranked AS (
    SELECT release_year, title, vote_average, vote_count,
           RANK() OVER (PARTITION BY release_year ORDER BY vote_average DESC) AS rk
    FROM v_movie_summary
    WHERE release_year >= 2000 AND vote_count >= 1000
)
SELECT release_year, title, vote_average, vote_count
FROM ranked
WHERE rk = 1
ORDER BY release_year;

-- name: q15_genre_pairs
-- question: Which genre combinations appear together most often?
SELECT g1.genre_name AS genre_a,
       g2.genre_name AS genre_b,
       COUNT(*)      AS films
FROM movie_genres a
JOIN movie_genres b ON a.movie_id = b.movie_id AND a.genre_id < b.genre_id
JOIN genres g1 ON g1.genre_id = a.genre_id
JOIN genres g2 ON g2.genre_id = b.genre_id
GROUP BY a.genre_id, b.genre_id
ORDER BY films DESC
LIMIT 15;

-- name: q16_cumulative_revenue_share
-- question: How concentrated is box office revenue? (Share earned by the top N% of films)
WITH r AS (
    SELECT revenue,
           ROW_NUMBER() OVER (ORDER BY revenue DESC) AS rn,
           COUNT(*)     OVER ()                      AS n,
           SUM(revenue) OVER ()                      AS total
    FROM v_movie_summary WHERE revenue IS NOT NULL
)
SELECT pct_of_films,
       ROUND(100.0 * SUM(revenue) / MAX(total), 1) AS pct_of_revenue
FROM (SELECT r.*, CASE WHEN rn <= n * 0.01 THEN 1
                       WHEN rn <= n * 0.05 THEN 5
                       WHEN rn <= n * 0.10 THEN 10
                       WHEN rn <= n * 0.20 THEN 20
                       WHEN rn <= n * 0.50 THEN 50 ELSE 100 END AS bucket
      FROM r) b
JOIN (SELECT 1 AS pct_of_films UNION ALL SELECT 5 UNION ALL SELECT 10
      UNION ALL SELECT 20 UNION ALL SELECT 50 UNION ALL SELECT 100) p
  ON b.bucket <= p.pct_of_films
GROUP BY pct_of_films
ORDER BY pct_of_films;

-- name: q17_non_english_films
-- question: How do non-English-language films compare, by language?
SELECT original_language,
       COUNT(*)                       AS films,
       ROUND(AVG(vote_average), 2)    AS avg_rating,
       ROUND(AVG(revenue) / 1e6, 1)   AS avg_revenue_m
FROM v_movie_summary
GROUP BY original_language
HAVING COUNT(*) >= 4
ORDER BY films DESC;

-- TMDB movies: normalised relational schema (SQLite, 3NF)
--
--   genres ──< movie_genres >── movies ──< movie_keywords >── keywords
--                                 │
--                    ┌────────────┴────────────┐
--               cast_credits              crew_credits ──> jobs
--                    └──────> people <─────────┘
--
-- Foreign keys are enforced (PRAGMA foreign_keys = ON in build_db.py).

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS crew_credits;
DROP TABLE IF EXISTS cast_credits;
DROP TABLE IF EXISTS movie_keywords;
DROP TABLE IF EXISTS movie_genres;
DROP TABLE IF EXISTS jobs;
DROP TABLE IF EXISTS people;
DROP TABLE IF EXISTS keywords;
DROP TABLE IF EXISTS genres;
DROP TABLE IF EXISTS movies;

CREATE TABLE movies (
    movie_id          INTEGER PRIMARY KEY,
    title             TEXT    NOT NULL,
    original_language TEXT    NOT NULL,
    release_date      TEXT    NOT NULL,          -- ISO 8601 date (YYYY-MM-DD)
    release_year      INTEGER NOT NULL,
    release_month     INTEGER NOT NULL CHECK (release_month BETWEEN 1 AND 12),
    decade            INTEGER NOT NULL,
    runtime           INTEGER NOT NULL CHECK (runtime > 0),
    budget            INTEGER NOT NULL CHECK (budget >= 0),   -- raw TMDB value; 0 = unknown
    revenue           INTEGER NOT NULL CHECK (revenue >= 0),  -- raw TMDB value; 0 = unknown
    popularity        REAL    NOT NULL,
    vote_average      REAL    NOT NULL CHECK (vote_average BETWEEN 0 AND 10),
    vote_count        INTEGER NOT NULL CHECK (vote_count >= 0),
    status            TEXT    NOT NULL,
    overview          TEXT
);

CREATE TABLE genres (
    genre_id   INTEGER PRIMARY KEY,
    genre_name TEXT NOT NULL UNIQUE
);

CREATE TABLE movie_genres (
    movie_id INTEGER NOT NULL REFERENCES movies(movie_id) ON DELETE CASCADE,
    genre_id INTEGER NOT NULL REFERENCES genres(genre_id),
    PRIMARY KEY (movie_id, genre_id)
);

CREATE TABLE keywords (
    keyword_id   INTEGER PRIMARY KEY,
    keyword_name TEXT NOT NULL
);

CREATE TABLE movie_keywords (
    movie_id   INTEGER NOT NULL REFERENCES movies(movie_id) ON DELETE CASCADE,
    keyword_id INTEGER NOT NULL REFERENCES keywords(keyword_id),
    PRIMARY KEY (movie_id, keyword_id)
);

CREATE TABLE people (
    person_id   INTEGER PRIMARY KEY,
    person_name TEXT NOT NULL
);

CREATE TABLE jobs (
    job_id     INTEGER PRIMARY KEY,
    job        TEXT NOT NULL UNIQUE,
    department TEXT NOT NULL
);

CREATE TABLE cast_credits (
    cast_id        INTEGER PRIMARY KEY,
    movie_id       INTEGER NOT NULL REFERENCES movies(movie_id) ON DELETE CASCADE,
    person_id      INTEGER NOT NULL REFERENCES people(person_id),
    character_name TEXT,
    cast_order     INTEGER NOT NULL CHECK (cast_order >= 0)   -- 0 = top billing
);

CREATE TABLE crew_credits (
    crew_id   INTEGER PRIMARY KEY,
    movie_id  INTEGER NOT NULL REFERENCES movies(movie_id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES people(person_id),
    job_id    INTEGER NOT NULL REFERENCES jobs(job_id),
    UNIQUE (movie_id, person_id, job_id)
);

-- Indexes on the foreign keys used by the analysis joins
CREATE INDEX idx_movie_genres_genre   ON movie_genres(genre_id);
CREATE INDEX idx_movie_keywords_kw    ON movie_keywords(keyword_id);
CREATE INDEX idx_cast_movie           ON cast_credits(movie_id);
CREATE INDEX idx_cast_person          ON cast_credits(person_id);
CREATE INDEX idx_crew_movie           ON crew_credits(movie_id);
CREATE INDEX idx_crew_person          ON crew_credits(person_id);
CREATE INDEX idx_movies_year          ON movies(release_year);

-- Analysis view: one row per film, unknown money as NULL, derived profit/ROI,
-- and its director(s) and genres flattened
DROP VIEW IF EXISTS v_movie_summary;
CREATE VIEW v_movie_summary AS
SELECT m.movie_id,
       m.title,
       m.release_year,
       m.release_month,
       m.decade,
       m.original_language,
       m.runtime,
       -- Unknown money (0, or revenue under $10k) becomes NULL here, so averages and
       -- ROI never treat "unknown" as "$0". The raw values stay untouched in `movies`.
       NULLIF(m.budget, 0)                                                AS budget,
       CASE WHEN m.revenue >= 10000 THEN m.revenue END                    AS revenue,
       CASE WHEN m.budget > 0 AND m.revenue >= 10000
            THEN m.revenue - m.budget END                                 AS profit,
       CASE WHEN m.budget > 0 AND m.revenue >= 10000
            THEN ROUND(1.0 * m.revenue / m.budget, 3) END                 AS roi,
       m.vote_average,
       m.vote_count,
       m.popularity,
       (SELECT group_concat(g.genre_name, ', ')
          FROM movie_genres mg JOIN genres g USING (genre_id)
         WHERE mg.movie_id = m.movie_id)                     AS genres,
       (SELECT group_concat(p.person_name, ', ')
          FROM crew_credits c
          JOIN jobs j   USING (job_id)
          JOIN people p USING (person_id)
         WHERE c.movie_id = m.movie_id AND j.job = 'Director') AS directors
FROM movies m;

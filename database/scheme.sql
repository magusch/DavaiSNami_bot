CREATE OR REPLACE FUNCTION date_from_to_date_to()
RETURNS TRIGGER AS
$$
BEGIN 
	UPDATE events SET date_to=events.date_from+ '2 hours' WHERE date_to is NULL;
	RETURN NEW;
END;
$$
LANGUAGE 'plpgsql';


CREATE TRIGGER empty_date_to AFTER INSERT ON events 
FOR EACH ROW EXECUTE PROCEDURE date_from_to_date_to();


CREATE TABLE IF NOT EXISTS "reminder" (
    "user_id" INTEGER,
    "title" TEXT NOT NULL,
    "post_id" INTEGER,
    "date" DATE
);

create table exhibitions
(
    post_id     integer
        unique,
    title       varchar(150),
    date_before timestamp
);

CREATE TABLE bot_users_general (
               user_id BIGINT PRIMARY KEY,
               nickname VARCHAR(50),
               first_name VARCHAR(50),
               last_name VARCHAR(50),
               is_admin BOOLEAN DEFAULT FALSE,
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
           )

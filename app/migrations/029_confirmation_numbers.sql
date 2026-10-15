-- Public lookup numbers are not credentials. UUID keys and issued QR payloads stay unchanged.
CREATE SEQUENCE IF NOT EXISTS {schema}.confirmation_number_seq
 AS BIGINT MINVALUE 10000000 MAXVALUE 99999999 START 10000000 NO CYCLE;
ALTER TABLE {schema}.registration_orders ADD COLUMN IF NOT EXISTS confirmation_number BIGINT;
ALTER TABLE {schema}.registration_orders ALTER COLUMN confirmation_number
 SET DEFAULT nextval('{schema}.confirmation_number_seq');
UPDATE {schema}.registration_orders SET confirmation_number=nextval('{schema}.confirmation_number_seq')
 WHERE confirmation_number IS NULL;
ALTER TABLE {schema}.registration_orders ALTER COLUMN confirmation_number SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS registration_confirmation_number_unique
 ON {schema}.registration_orders(confirmation_number);
CREATE OR REPLACE FUNCTION {schema}.preserve_confirmation_number() RETURNS trigger AS $$
BEGIN
 IF NEW.confirmation_number < 10000000 OR NEW.confirmation_number > 99999999 THEN
  RAISE EXCEPTION 'Confirmation number must contain eight digits';
 END IF;
 IF TG_OP = 'UPDATE' AND NEW.confirmation_number IS DISTINCT FROM OLD.confirmation_number THEN
  RAISE EXCEPTION 'Confirmation number cannot change';
 END IF;
 RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS preserve_confirmation_number ON {schema}.registration_orders;
CREATE TRIGGER preserve_confirmation_number BEFORE INSERT OR UPDATE ON {schema}.registration_orders
 FOR EACH ROW EXECUTE FUNCTION {schema}.preserve_confirmation_number();

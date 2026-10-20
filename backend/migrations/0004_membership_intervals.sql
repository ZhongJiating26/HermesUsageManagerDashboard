CREATE TRIGGER membership_no_overlap_insert BEFORE INSERT ON department_membership
WHEN NEW.valid_to IS NOT NULL AND NEW.valid_to<=NEW.valid_from
OR EXISTS(SELECT 1 FROM department_membership old WHERE old.user_id=NEW.user_id AND old.valid_from<coalesce(NEW.valid_to,'9999') AND coalesce(old.valid_to,'9999')>NEW.valid_from)
BEGIN
SELECT RAISE(ABORT,'Overlapping membership interval');
END;
CREATE TRIGGER membership_no_overlap_update BEFORE UPDATE ON department_membership
WHEN NEW.valid_to IS NOT NULL AND NEW.valid_to<=NEW.valid_from
OR EXISTS(SELECT 1 FROM department_membership old WHERE old.id<>NEW.id AND old.user_id=NEW.user_id AND old.valid_from<coalesce(NEW.valid_to,'9999') AND coalesce(old.valid_to,'9999')>NEW.valid_from)
BEGIN
SELECT RAISE(ABORT,'Overlapping membership interval');
END;

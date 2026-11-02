-- Run once after 007; historical applications stay unrouted unless explicitly reviewed.
ALTER TABLE applications
  ADD COLUMN assignment_id INT NULL,
  ADD COLUMN working_candidate_id INT NULL,
  ADD COLUMN working_resume_id INT NULL,
  ADD CONSTRAINT fk_application_assignment FOREIGN KEY (assignment_id) REFERENCES job_assignments(id),
  ADD CONSTRAINT fk_application_working_candidate FOREIGN KEY (working_candidate_id) REFERENCES candidates(id),
  ADD CONSTRAINT fk_application_working_resume FOREIGN KEY (working_resume_id) REFERENCES resumes(id);

# RegFire isolated staging

This directory is a reviewable staging release, not proof of an AWS deployment. Corporate Netlify, local attendee records, and mail DNS are outside its scope.

## Concrete topology

Use the verified Regfire AWS project in us-east-2. `staging.json` defines an isolated VPC, HTTPS ALB, one 0.5-vCPU/1-GB Fargate task running Gunicorn, private encrypted RDS PostgreSQL 17.11 (db.t4g.micro, 20 GB gp3, seven-day backups), and encrypted EFS uploads with IAM access-point isolation and automatic backup. Database and filesystem retain their data on stack replacement/deletion. The task has a public IP for outbound image retrieval but its security group accepts application traffic only from the ALB. Private database subnets have no Internet route. No NAT gateway is created.

Supply a separately approved staging hostname, its Ohio ACM certificate ARN, ECR repository ARN and immutable image digest, and the ARN of a private staging-owner bootstrap password. Do not use the marketing apex as the registration origin. No credentials belong in source, command history, templates, stack outputs or logs.

`DesiredCount` defaults to zero. The web task cannot read the master database or owner-bootstrap secrets. The migration task has those permissions and must run explicitly before the service is started. It initializes schema and owner, creates the restricted runtime role, and grants table DML/sequence access. The application performs read-only startup checks and will not bootstrap an owner or run migrations in production mode.

EFS is mounted only at `/app/uploads`, through a UID/GID 10001 access point. Existing application authorization still controls every download. `/app/.local` and `/tmp` are ephemeral task volumes. Entry-point materialization writes only the task's restricted PostgreSQL credential with mode 0600, then drops to UID 10001. No Mac private settings, Bird key, payment configuration, Wallet key, event database, or uploads enter the image.

## Attendee boundary

Only UUIDs explicitly listed in `EnabledSyntheticFlows` are available through `/api/public/events/...`. Default is empty. Use synthetic flows only. Attendee email/password in the existing form creates or authenticates the attendee account; no organizer grants or duplicate signup screen are added. Existing passwords cannot be replaced by registration. Completed checkout belongs to that attendee ID; colleague registrations remain individually confirmed without creating or taking over their accounts. Exact flow, actor ownership and attendee CSRF checks protect checkout. Organizer APIs remain protected. Preview definition overrides are replaced with saved server definitions.

This is deliberately staging-only publication control. A production organizer publish/unpublish workflow, multi-replica rate limits, MFA and production security review remain launch gates. Do not migrate real attendee data into this staging release.

## Build and release procedure

1. Validate `staging.json` with cfn-lint and cfn-guard before provisioning. AWS `validate-template` checks syntax only; it does not establish resource compatibility or security compliance.
2. Build from the app directory: `docker build --platform linux/amd64 -f deploy/Dockerfile -t regfire-staging:<release> .`. Inspect the image file list: `.dockerignore` is an allowlist and excludes all runtime/test/private files.
3. Push to an approved private ECR repository, record its SHA256 digest, and use that digest for both task definitions. CodeBuild built and pushed the image successfully; local Docker is unavailable. Record scan findings separately before starting tasks.
4. Obtain approval for costs, hostname/DNS and new staging secrets/service roles. Deploy `staging.json` with desired count zero in us-east-2 only. No deployment command should silently accept IAM capabilities or supply credentials in plain parameters.
5. Run `MigrationTask` once in the task subnets/security group with outbound access. Require exit code zero and inspect its redacted logs. Do not run the migration using the runtime role.
6. After migration, start one task with the public flow allowlist empty. Create only synthetic test flows using the protected staging organizer, then set their IDs in `EnabledSyntheticFlows`. Verify the certificate and canonical Host before opening the site. Do not bypass TLS warnings.
7. Verify `/health/ready` using the canonical HTTPS host, attendee signup/existing login, group checkout with individual IDs, cross-account and cross-event denial, CSRF, upload permissions, and PDF/QR identifiers-only behavior. Use free registration and mocked paid-provider tests. External payment requests are blocked when `REGFIRE_STAGING=1`; mail-live switches are removed at startup.
8. Confirm RDS backup recovery into a separate retained database and EFS recovery into a separate access point. Verify restored synthetic order and upload checksums before cleanup. Local synthetic PostgreSQL dump/restore proof is separate from this required AWS restore exercise.

## Rollback

Record the prior image digest and ECS task-definition ARN before each release. With a compatible schema, update the service back to that task definition and wait for stable healthy targets. Deployment circuit-breaker rollback is enabled, but verify its outcome rather than assuming success. Never auto-downgrade schema. For incompatible migrations, keep the previous data store, restore into a new private database/filesystem, run validation, then explicitly switch the runtime configuration. Never restore over the working database or delete the retained resources to roll back code.

## Monitoring and outstanding cloud verification

Application logging records status and method only: no raw URL, query, body, cookie, exception content, or attendee answers. CloudWatch retains logs for 14 days. An unhealthy-target alarm is defined without external notifications. Add approved notification destinations and CloudTrail/data-event coverage during deployment review; these are not claimed configured. ACM issued the staging certificate after DNS validation. End-to-end HTTPS, IAM/least-privilege behavior, live backups, AWS restore, provider approval and live delivery still require separate evidence.

The first app-stack attempt was rejected by RDS because the Free plan does not permit the configured seven-day backup retention. Do not silently weaken that retention or upgrade billing. The build stack succeeded; the app stack rolled back before any application task ran. Retained resources must be inventoried before retrying to avoid orphaned duplicate storage/secrets.

Price estimate and execution evidence are kept in the local `work/aws-readiness` directory. No email sending or real payment operation is authorized by this package.

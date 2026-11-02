> ## Documentation Index
> Fetch the complete documentation index at: https://docs.fireworks.ai/llms.txt
> Use this file to discover all available pages before exploring further.

> Create a supervised fine-tuning job via the Fireworks API, submitting training datasets, hyperparameters, and model configuration for managed SFT runs.

# Create Supervised Fine-tuning Job

## Learning rate scheduler

Supervised fine-tuning jobs accept an optional `lrScheduler` object on the request body. Set **exactly one** of `constant`, `linear`, or `cosine`. When omitted, the trainer uses a constant learning rate after warmup.

Configure warmup separately with `learningRateWarmupSteps` (not inside `lrScheduler`).

| Schedule | Object shape | Notes |
| - | - | - |
| `constant` | `{ "constant": {} }` | Flat LR after warmup |
| `linear` | `{ "linear": { "minLrRatio": 0.1, "decayRatio": 0.8 } }` | Linear decay toward `learningRate * minLrRatio` |
| `cosine` | `{ "cosine": { "minLrRatio": 0.1, "decayRatio": 0.8 } }` | Cosine annealing toward `learningRate * minLrRatio` |

For `linear` and `cosine`:

* `minLrRatio` — floor LR as a fraction of `learningRate` (0.0–1.0).
* `decayRatio` — fraction of total training steps over which to decay. Omit or set `0` to decay over the full run.

`linear` and `cosine` require a base model on the **Training V2** path. V1-routed models only support a constant schedule.

### Example: cosine schedule

```json theme={null}
{
  "supervisedFineTuningJob": {
    "baseModel": "accounts/my-account/models/qwen3-8b",
    "dataset": "accounts/my-account/datasets/my-data",
    "outputModel": "accounts/my-account/models/my-tuned-model",
    "learningRate": 0.0001,
    "learningRateWarmupSteps": 10,
    "lrScheduler": {
      "cosine": {
        "minLrRatio": 0.1,
        "decayRatio": 0.8
      }
    }
  }
}
```

See also [Training models](https://docs.fireworks.ai/fine-tuning/fine-tuning-models.md) for CLI equivalents (`--learning-rate-scheduler`, `--learning-rate-min-lr-ratio`, `--learning-rate-decay-ratio`).


## OpenAPI

````yaml post /v1/accounts/{account_id}/supervisedFineTuningJobs
openapi: 3.1.0
info:
  title: Gateway REST API
  version: 5.10.0
servers:
  - url: https://api.fireworks.ai
security:
  - BearerAuth: []
tags:
  - name: AccountService
  - name: DeploymentService
  - name: Gateway
  - name: ModelService
  - name: TrainingService
paths:
  /v1/accounts/{account_id}/supervisedFineTuningJobs:
    post:
      tags:
        - Gateway
      summary: Create Supervised Fine-tuning Job
      operationId: Gateway_CreateSupervisedFineTuningJob
      parameters:
        - name: supervisedFineTuningJobId
          description: >-
            ID of the supervised fine-tuning job, a random UUID will be
            generated if not specified.
          in: query
          required: false
          schema:
            type: string
        - name: account_id
          in: path
          required: true
          description: The Account Id
          schema:
            type: string
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/gatewaySupervisedFineTuningJob'
        required: true
      responses:
        '200':
          description: A successful response.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/gatewaySupervisedFineTuningJob'
components:
  schemas:
    gatewaySupervisedFineTuningJob:
      type: object
      properties:
        name:
          type: string
          readOnly: true
        displayName:
          type: string
        createTime:
          type: string
          format: date-time
          readOnly: true
        completedTime:
          type: string
          format: date-time
          readOnly: true
        dataset:
          type: string
          description: The name of the dataset used for training.
        awsS3Config:
          $ref: '#/components/schemas/gatewayAwsS3Config'
          description: The AWS configuration for S3 dataset access.
        azureBlobStorageConfig:
          $ref: '#/components/schemas/gatewayAzureBlobStorageConfig'
          description: The Azure configuration for Azure Blob Storage dataset access.
        state:
          $ref: '#/components/schemas/gatewayJobState'
          readOnly: true
        status:
          $ref: '#/components/schemas/gatewayStatus'
          readOnly: true
        createdBy:
          type: string
          description: The email address of the user who initiated this fine-tuning job.
          readOnly: true
        outputModel:
          type: string
          description: >-
            The model ID to be assigned to the resulting fine-tuned model. If
            not specified, the job ID will be used.
        baseModel:
          type: string
          description: |-
            The name of the base model to be fine-tuned
            Only one of 'base_model' or 'warm_start_from' should be specified.
        warmStartFrom:
          type: string
          description: |-
            The PEFT addon model in Fireworks format to be fine-tuned from
            Only one of 'base_model' or 'warm_start_from' should be specified.
        jinjaTemplate:
          type: string
          description: >-
            Deprecated: literal Jinja templates are not supported by Training
            V2.

            Conversation rendering is selected from the base model's registered

            renderer configuration instead.
        earlyStop:
          type: boolean
          description: 'Deprecated: early stopping is not supported by managed training.'
        epochs:
          type: integer
          format: int32
          description: The number of epochs to train for.
        learningRate:
          type: number
          format: float
          description: The learning rate used for training.
        maxContextLength:
          type: integer
          format: int32
          description: The maximum context length to use with the model.
        loraRank:
          type: integer
          format: int32
          description: The rank of the LoRA layers.
        wandbConfig:
          $ref: '#/components/schemas/gatewayWandbConfig'
          description: >-
            The Weights & Biases team/user account for logging training
            progress.
        evaluationDataset:
          type: string
          description: The name of a separate dataset to use for evaluation.
        isTurbo:
          type: boolean
          description: Whether to run the fine-tuning job in turbo mode.
        evalAutoCarveout:
          type: boolean
          description: Whether to auto-carve the dataset for eval.
        updateTime:
          type: string
          format: date-time
          description: The update time for the supervised fine-tuning job.
          readOnly: true
        nodes:
          type: integer
          format: int32
          description: |-
            Deprecated: multi-node scheduling is now handled by the cookbook
            orchestrator in V2 workflows. This field is ignored for V2 jobs and
            will be removed in a future release.
        batchSize:
          type: integer
          format: int32
          description: >-
            Deprecated: legacy V1 token budget. Training V2 batches by samples
            via

            batch_size_samples.
        mtpEnabled:
          type: boolean
          description: >-
            Deprecated: MTP is no longer supported by managed training. This
            field is

            retained for API wire compatibility only.
        mtpNumDraftTokens:
          type: integer
          format: int32
          description: 'Deprecated: see mtp_enabled.'
        mtpFreezeBaseModel:
          type: boolean
          description: 'Deprecated: see mtp_enabled.'
        jobProgress:
          $ref: '#/components/schemas/gatewayJobProgress'
          description: Job progress.
          readOnly: true
        metricsFileSignedUrl:
          type: string
          title: The signed URL for the metrics file
        trainerLogsSignedUrl:
          type: string
          description: |-
            The signed URL for the trainer logs file (stdout/stderr).
            Only populated if the account has trainer log reading enabled.
          readOnly: true
        renderSamplesSignedUrl:
          type: string
          description: The signed URL for orchestrator-rendered token IDs and loss masks.
          readOnly: true
        gradientAccumulationSteps:
          type: integer
          format: int32
          description: |-
            Deprecated: legacy V1 gradient accumulation. Training V2 batches by
            samples via batch_size_samples and rejects this field when set.
        learningRateWarmupSteps:
          type: integer
          format: int32
          title: Number of steps for learning rate warm up
        lrScheduler:
          $ref: '#/components/schemas/gatewayLearningRateScheduler'
          description: >-
            The learning-rate schedule (constant/linear/cosine + per-type
            knobs).

            When unset, the trainer uses the legacy constant schedule.
        batchSizeSamples:
          type: integer
          format: int32
          description: The number of samples per gradient batch.
        estimatedCost:
          $ref: '#/components/schemas/typeMoney'
          description: The estimated cost of the job.
          readOnly: true
        optimizerWeightDecay:
          type: number
          format: float
          description: Weight decay (L2 regularization) for optimizer.
        purpose:
          $ref: '#/components/schemas/gatewayPurpose'
          description: Scheduling purpose for this job.
        encryptionState:
          $ref: '#/components/schemas/gatewayEncryptionState'
          description: CMEK encryption state (authoritative, stamped at creation).
          readOnly: true
      required:
        - dataset
    gatewayAwsS3Config:
      type: object
      properties:
        credentialsSecret:
          type: string
          title: >-
            Reference to a Secret resource containing AWS access key
            credentials.

            Format: accounts/{account_id}/secrets/{secret_id}

            The secret value must be JSON: {"aws_access_key_id": "AKIA...",
            "aws_secret_access_key": "..."}
        iamRoleArn:
          type: string
          title: >-
            IAM role ARN to assume for accessing S3 datasets via GCP OIDC
            federation.

            Format: arn:aws:iam::account-id:role/role-name
      description: |-
        AwsS3Config is the configuration for AWS S3 dataset access which
        will be used by a training job.
    gatewayAzureBlobStorageConfig:
      type: object
      properties:
        credentialsSecret:
          type: string
          description: >-
            Reference to a Secret resource containing Azure credentials.

            Format: accounts/{account_id}/secrets/{secret_id}

            The secret value must be JSON: {"connection_string": "..."} or
            {"sas_token": "..."} or {"account_key": "..."}

            Mutually exclusive with managed_identity_client_id.
        managedIdentityClientId:
          type: string
          description: >-
            Managed Identity Client ID for GCP-to-Azure Workload Identity
            Federation.

            Format: uuid

            Mutually exclusive with credentials_secret.
        tenantId:
          type: string
          title: |-
            Azure tenant ID for Workload Identity Federation.
            Format: uuid
      description: >-
        AzureBlobStorageConfig is the configuration for Azure Blob Storage
        dataset access

        which will be used by a training job.
    gatewayJobState:
      type: string
      enum:
        - JOB_STATE_UNSPECIFIED
        - JOB_STATE_CREATING
        - JOB_STATE_RUNNING
        - JOB_STATE_COMPLETED
        - JOB_STATE_FAILED
        - JOB_STATE_CANCELLED
        - JOB_STATE_DELETING
        - JOB_STATE_WRITING_RESULTS
        - JOB_STATE_VALIDATING
        - JOB_STATE_DELETING_CLEANING_UP
        - JOB_STATE_PENDING
        - JOB_STATE_EXPIRED
        - JOB_STATE_RE_QUEUEING
        - JOB_STATE_CREATING_INPUT_DATASET
        - JOB_STATE_IDLE
        - JOB_STATE_CANCELLING
        - JOB_STATE_EARLY_STOPPED
        - JOB_STATE_PAUSED
        - JOB_STATE_DELETED
        - JOB_STATE_ARCHIVED
      default: JOB_STATE_UNSPECIFIED
      description: |-
        JobState represents the state an asynchronous job can be in.

         - JOB_STATE_PAUSED: Job is paused, typically due to account suspension or manual intervention.
         - JOB_STATE_DELETED: Job has been deleted.
         - JOB_STATE_ARCHIVED: User-facing state for jobs whose row is retained post-delete (e.g. RLOR
        trainers within the checkpoint retention window). The internal row is
        still in JOB_STATE_DELETED; the gateway translates it to ARCHIVED on
        public responses.
    gatewayStatus:
      type: object
      properties:
        code:
          $ref: '#/components/schemas/gatewayCode'
          description: The status code.
        message:
          type: string
          description: A developer-facing error message in English.
      title: >-
        Mimics
        [https://github.com/googleapis/googleapis/blob/master/google/rpc/status.proto]
    gatewayWandbConfig:
      type: object
      properties:
        enabled:
          type: boolean
          description: Whether to enable wandb logging.
        apiKey:
          type: string
          description: The API key for the wandb service.
        project:
          type: string
          description: The project name for the wandb service.
        entity:
          type: string
          description: The entity name for the wandb service.
        runId:
          type: string
          description: The run ID for the wandb service.
        url:
          type: string
          description: The URL for the wandb service.
          readOnly: true
      description: >-
        WandbConfig is the configuration for the Weights & Biases (wandb)
        logging which

        will be used by a training job.
    gatewayJobProgress:
      type: object
      properties:
        percent:
          type: integer
          format: int32
          description: Progress percent, within the range from 0 to 100.
        epoch:
          type: integer
          format: int32
          description: >-
            The epoch for which the progress percent is reported, usually
            starting from 0.

            This is optional for jobs that don't run in an epoch fasion, e.g.
            BIJ, EVJ.
        totalInputRequests:
          type: integer
          format: int32
          description: Total number of input requests/rows in the job.
        totalProcessedRequests:
          type: integer
          format: int32
          description: >-
            Total number of requests that have been processed (successfully or
            failed).
        successfullyProcessedRequests:
          type: integer
          format: int32
          description: Number of requests that were processed successfully.
        failedRequests:
          type: integer
          format: int32
          description: Number of requests that failed to process.
        outputRows:
          type: integer
          format: int32
          description: Number of output rows generated.
        inputTokens:
          type: integer
          format: int32
          description: Total number of input tokens processed.
        outputTokens:
          type: integer
          format: int32
          description: Total number of output tokens generated.
        cachedInputTokenCount:
          type: integer
          format: int32
          description: The number of input tokens that hit the prompt cache.
      description: Progress of a job, e.g. RLOR, EVJ, BIJ etc.
    gatewayLearningRateScheduler:
      type: object
      properties:
        constant:
          $ref: '#/components/schemas/gatewayConstantLRSchedule'
        linear:
          $ref: '#/components/schemas/gatewayLinearLRSchedule'
        cosine:
          $ref: '#/components/schemas/gatewayCosineLRSchedule'
      description: >-
        Learning-rate scheduler applied on top of the base learning rate (after
        the

        shared learning_rate_warmup_steps warmup). It mirrors the trainer-side

        fireworks.training.sdk.training_spec.LRSchedulerSpec discriminated
        union:

        the schedule variant that is set selects the shape, and each variant
        carries

        only the knobs that apply to it. Add a new schedule by adding a message
        and

        one `oneof schedule` entry; existing clients are unaffected. When unset,

        the trainer uses the legacy constant schedule.
    typeMoney:
      type: object
      properties:
        currencyCode:
          type: string
          description: The three-letter currency code defined in ISO 4217.
        units:
          type: string
          format: int64
          description: >-
            The whole units of the amount.

            For example if `currencyCode` is `"USD"`, then 1 unit is one US
            dollar.
        nanos:
          type: integer
          format: int32
          description: >-
            Number of nano (10^-9) units of the amount.

            The value must be between -999,999,999 and +999,999,999 inclusive.

            If `units` is positive, `nanos` must be positive or zero.

            If `units` is zero, `nanos` can be positive, zero, or negative.

            If `units` is negative, `nanos` must be negative or zero.

            For example $-1.75 is represented as `units`=-1 and
            `nanos`=-750,000,000.
      description: Represents an amount of money with its currency type.
    gatewayPurpose:
      type: string
      enum:
        - PURPOSE_UNSPECIFIED
        - PURPOSE_PILOT
      default: PURPOSE_UNSPECIFIED
      description: Scheduling purpose for training jobs and deployments.
    gatewayEncryptionState:
      type: string
      enum:
        - ENCRYPTION_STATE_UNSPECIFIED
        - ENCRYPTION_STATE_PLAINTEXT
        - ENCRYPTION_STATE_CMEK
      default: ENCRYPTION_STATE_UNSPECIFIED
      description: >-
        EncryptionState is the authoritative, per-resource CMEK marker: the
        single

        source of truth for whether a resource's customer-data artifacts are

        encrypted. It is stamped at resource creation from the owning account's
        CMEK

        config and is immutable for the resource's life, so a resource always
        reads

        back with the state it was created under regardless of the account's
        current

        flag. The encrypt-on-write / decrypt-on-read decision for the resource's

        data keys off this field.

         - ENCRYPTION_STATE_UNSPECIFIED: Unstamped/legacy rows that predate CMEK. Treated as PLAINTEXT.
         - ENCRYPTION_STATE_PLAINTEXT: Customer-data artifacts are stored as plaintext (Fireworks-owned, no CMEK).
         - ENCRYPTION_STATE_CMEK: Customer-data artifacts are CMEK-encrypted; reads MUST decrypt (fail-closed).
    gatewayCode:
      type: string
      enum:
        - OK
        - CANCELLED
        - UNKNOWN
        - INVALID_ARGUMENT
        - DEADLINE_EXCEEDED
        - NOT_FOUND
        - ALREADY_EXISTS
        - PERMISSION_DENIED
        - UNAUTHENTICATED
        - RESOURCE_EXHAUSTED
        - FAILED_PRECONDITION
        - ABORTED
        - OUT_OF_RANGE
        - UNIMPLEMENTED
        - INTERNAL
        - UNAVAILABLE
        - DATA_LOSS
      default: OK
      description: |-
        - OK: Not an error; returned on success.

        HTTP Mapping: 200 OK
         - CANCELLED: The operation was cancelled, typically by the caller.

        HTTP Mapping: 499 Client Closed Request
         - UNKNOWN: Unknown error.  For example, this error may be returned when
        a `Status` value received from another address space belongs to
        an error space that is not known in this address space.  Also
        errors raised by APIs that do not return enough error information
        may be converted to this error.

        HTTP Mapping: 500 Internal Server Error
         - INVALID_ARGUMENT: The client specified an invalid argument.  Note that this differs
        from `FAILED_PRECONDITION`.  `INVALID_ARGUMENT` indicates arguments
        that are problematic regardless of the state of the system
        (e.g., a malformed file name).

        HTTP Mapping: 400 Bad Request
         - DEADLINE_EXCEEDED: The deadline expired before the operation could complete. For operations
        that change the state of the system, this error may be returned
        even if the operation has completed successfully.  For example, a
        successful response from a server could have been delayed long
        enough for the deadline to expire.

        HTTP Mapping: 504 Gateway Timeout
         - NOT_FOUND: Some requested entity (e.g., file or directory) was not found.

        Note to server developers: if a request is denied for an entire class
        of users, such as gradual feature rollout or undocumented allowlist,
        `NOT_FOUND` may be used. If a request is denied for some users within
        a class of users, such as user-based access control, `PERMISSION_DENIED`
        must be used.

        HTTP Mapping: 404 Not Found
         - ALREADY_EXISTS: The entity that a client attempted to create (e.g., file or directory)
        already exists.

        HTTP Mapping: 409 Conflict
         - PERMISSION_DENIED: The caller does not have permission to execute the specified
        operation. `PERMISSION_DENIED` must not be used for rejections
        caused by exhausting some resource (use `RESOURCE_EXHAUSTED`
        instead for those errors). `PERMISSION_DENIED` must not be
        used if the caller can not be identified (use `UNAUTHENTICATED`
        instead for those errors). This error code does not imply the
        request is valid or the requested entity exists or satisfies
        other pre-conditions.

        HTTP Mapping: 403 Forbidden
         - UNAUTHENTICATED: The request does not have valid authentication credentials for the
        operation.

        HTTP Mapping: 401 Unauthorized
         - RESOURCE_EXHAUSTED: Some resource has been exhausted, perhaps a per-user quota, or
        perhaps the entire file system is out of space.

        HTTP Mapping: 429 Too Many Requests
         - FAILED_PRECONDITION: The operation was rejected because the system is not in a state
        required for the operation's execution.  For example, the directory
        to be deleted is non-empty, an rmdir operation is applied to
        a non-directory, etc.

        Service implementors can use the following guidelines to decide
        between `FAILED_PRECONDITION`, `ABORTED`, and `UNAVAILABLE`:
         (a) Use `UNAVAILABLE` if the client can retry just the failing call.
         (b) Use `ABORTED` if the client should retry at a higher level. For
             example, when a client-specified test-and-set fails, indicating the
             client should restart a read-modify-write sequence.
         (c) Use `FAILED_PRECONDITION` if the client should not retry until
             the system state has been explicitly fixed. For example, if an "rmdir"
             fails because the directory is non-empty, `FAILED_PRECONDITION`
             should be returned since the client should not retry unless
             the files are deleted from the directory.

        HTTP Mapping: 400 Bad Request
         - ABORTED: The operation was aborted, typically due to a concurrency issue such as
        a sequencer check failure or transaction abort.

        See the guidelines above for deciding between `FAILED_PRECONDITION`,
        `ABORTED`, and `UNAVAILABLE`.

        HTTP Mapping: 409 Conflict
         - OUT_OF_RANGE: The operation was attempted past the valid range.  E.g., seeking or
        reading past end-of-file.

        Unlike `INVALID_ARGUMENT`, this error indicates a problem that may
        be fixed if the system state changes. For example, a 32-bit file
        system will generate `INVALID_ARGUMENT` if asked to read at an
        offset that is not in the range [0,2^32-1], but it will generate
        `OUT_OF_RANGE` if asked to read from an offset past the current
        file size.

        There is a fair bit of overlap between `FAILED_PRECONDITION` and
        `OUT_OF_RANGE`.  We recommend using `OUT_OF_RANGE` (the more specific
        error) when it applies so that callers who are iterating through
        a space can easily look for an `OUT_OF_RANGE` error to detect when
        they are done.

        HTTP Mapping: 400 Bad Request
         - UNIMPLEMENTED: The operation is not implemented or is not supported/enabled in this
        service.

        HTTP Mapping: 501 Not Implemented
         - INTERNAL: Internal errors.  This means that some invariants expected by the
        underlying system have been broken.  This error code is reserved
        for serious errors.

        HTTP Mapping: 500 Internal Server Error
         - UNAVAILABLE: The service is currently unavailable.  This is most likely a
        transient condition, which can be corrected by retrying with
        a backoff. Note that it is not always safe to retry
        non-idempotent operations.

        See the guidelines above for deciding between `FAILED_PRECONDITION`,
        `ABORTED`, and `UNAVAILABLE`.

        HTTP Mapping: 503 Service Unavailable
         - DATA_LOSS: Unrecoverable data loss or corruption.

        HTTP Mapping: 500 Internal Server Error
      title: >-
        Mimics
        [https://github.com/googleapis/googleapis/blob/master/google/rpc/code.proto]
    gatewayConstantLRSchedule:
      type: object
      description: >-
        Constant learning rate held flat after warmup (legacy default). No decay
        knobs.
    gatewayLinearLRSchedule:
      type: object
      properties:
        minLrRatio:
          type: number
          format: float
          description: >-
            Floor learning rate as a fraction of the peak learning rate (0.0 =
            decay to

            zero, 0.1 = decay to 10% of the peak learning rate).
        decayRatio:
          type: number
          format: float
          description: >-
            Fraction of total training steps over which to decay. 0 (unset)
            decays

            over the full run.
      description: >-
        Linear decay from the peak learning rate toward min_lr_ratio after
        warmup.
    gatewayCosineLRSchedule:
      type: object
      properties:
        minLrRatio:
          type: number
          format: float
          description: >-
            Floor learning rate as a fraction of the peak learning rate (0.0 =
            decay to

            zero, 0.1 = decay to 10% of the peak learning rate).
        decayRatio:
          type: number
          format: float
          description: >-
            Fraction of total training steps over which to decay. 0 (unset)
            decays

            over the full run.
      description: >-
        Cosine annealing from the peak learning rate toward min_lr_ratio after
        warmup.
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      description: >-
        Bearer authentication using your Fireworks API key. Format: Bearer
        <API_KEY>
      bearerFormat: API_KEY

````
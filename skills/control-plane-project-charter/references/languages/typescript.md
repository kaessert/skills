# TypeScript

TypeScript composition functions, for projects that already use them.

> ### The `up` CLI does not support TypeScript yet — work around it, don't be surprised by it
>
> Verified against `up` directly:
>
> ```
> $ up function generate f --language typescript
> up: error: --language must be one of "go","go-templating","kcl","python" but got "typescript"
> ```
>
> The same holds for `up test generate` (which adds `yaml`) and `up project init`. There is no
> TypeScript entry in the CLI's language-image table and no TypeScript function builder, so a
> `functions/<n>/` directory containing a `package.json` fails `up project build` with
> **`no suitable builder found`**.
>
> **What still works, and is how TypeScript projects run today:**
>
> | | |
> |---|---|
> | The function | hand-maintained. Copy the layout in Part 2 — `main.ts` (gRPC bootstrap, don't edit) + `function.ts` (your logic) + `package.json` + `tsconfig.json` |
> | Building it | `npm install && npm run build` produces `dist/`, then package and push the image yourself. `up project build` will not do it for you |
> | Tests | write them in **YAML** ([`yaml.md`](yaml.md)) — the fallback test language, since the CLI has no TypeScript one ([`control-plane-project-charter` §10](../../SKILL.md#10-language-dispatch)). KCL ([`kcl.md`](kcl.md)) also works; both are fully supported, and they assert against the rendered output regardless of what produced it |
> | Everything else | unchanged — the v2 rules, the namespaced APIs, the TDD loop all apply exactly as they do to a KCL or Python function |
>
> Treat a missing CLI path as a manual step, not a blocker. Say in your summary which steps
> you had to do by hand, so the gap stays visible.

The language-agnostic rules — the TDD loop, what a v2 managed resource needs, what a green
run proves, reporting discipline — are in [`control-plane-project-charter`](../../SKILL.md) and are **not**
repeated here.

| | |
|---|---|
| Scaffold a function | by hand — see the box above and Part 2 |
| Compile (**required** before anything else) | `npm install && npm run build` |
| Type-check only | `npx tsc --noEmit` |
| Tests | `up test generate <n> --language yaml` (or `kcl`) |

---

# Part 1 — API versions and types

**Use the namespaced `.m.` API groups** — see
[`control-plane-project-charter` §5](../../SKILL.md#5-crossplane-v2-what-a-composed-resource-actually-needs).
TypeScript carries them as plain `apiVersion` strings, and the generated types live under the
`model/_schemas/` symlink.

### API Version Examples by Provider

```typescript
// AWS (namespaced)
const awsApiVersion = 'aws.m.upbound.io/v1beta1';

// Azure (namespaced)
const azureApiVersion = 'azure.m.upbound.io/v1beta1';

// GCP (namespaced)
const gcpApiVersion = 'gcp.m.upbound.io/v1beta1';
```

---

---

# Part 2 — Project structure

## Project Structure

```
functions/<composition-name>/
├── main.ts              # Entry point - gRPC server bootstrap
├── function.ts          # FunctionHandler implementation
├── package.json         # Dependencies and build scripts
├── tsconfig.json        # TypeScript compiler configuration
├── model/               # Symlink to generated schemas
│   └── _schemas/        # TypeScript types from CRDs
├── dist/                # Compiled JavaScript (after npm run build)
└── node_modules/        # Dependencies (after npm install)
```

**Key Rules:**
- `main.ts` = gRPC server bootstrap only (DO NOT modify)
- `function.ts` = all composition logic (implement `FunctionHandler`)
- Always run `npm install` then `npm run build` before testing
- Use generated schemas from `model/_schemas/` for type safety


## Critical SDK Components

```typescript
// Core imports from SDK
import {
  FunctionHandler,
  RunFunctionRequest,
  RunFunctionResponse,
  FunctionRunner,
  newGrpcServer,
  startServer,
  // Resource utilities
  getObservedCompositeResource,
  getDesiredCompositeResource,
  getObservedComposedResources,
  getDesiredComposedResources,
  setDesiredComposedResources,
  // Response utilities
  to,
  normal,
  fatal,
  // Types
  Resource,
  Logger
} from '@crossplane-org/function-sdk-typescript';
```


---

# Part 3 — Composition functions

## Pattern 1: FunctionHandler Structure

**When to use**: Every composition function

### Canonical Template

```typescript
import {
  FunctionHandler,
  RunFunctionRequest,
  RunFunctionResponse,
  getObservedCompositeResource,
  getDesiredCompositeResource,
  getDesiredComposedResources,
  getObservedComposedResources,
  setDesiredComposedResources,
  to,
  normal,
  fatal,
  Resource,
  Logger
} from '@crossplane-org/function-sdk-typescript';

// Type definitions for your XR
interface MyResourceSpec {
  region: string;
  enableFeature?: boolean;
  items?: string[];
  tags?: Record<string, string>;
}

interface MyResourceStatus {
  state?: string;
  message?: string;
}

export class Function implements FunctionHandler {
  async RunFunction(
    req: RunFunctionRequest,
    logger?: Logger
  ): Promise<RunFunctionResponse> {
    const start = Date.now();

    try {
      // Initialize response
      let rsp = to(req);

      // Extract resources
      const oxr = getObservedCompositeResource(req);
      const dxr = getDesiredCompositeResource(req);
      const desired = getDesiredComposedResources(req);
      const observed = getObservedComposedResources(req);

      // Type-safe spec access
      const spec = oxr?.resource?.spec as MyResourceSpec;
      const resourceName = oxr?.resource?.metadata?.name ?? 'default';

      // Generate resources
      // ... (implementation)

      // Return response
      rsp = setDesiredComposedResources(rsp, desired);
      normal(rsp, 'Processing complete');

      logger?.info({ duration: Date.now() - start }, 'Success');
      return rsp;

    } catch (error) {
      const rsp = to(req);
      fatal(rsp, error instanceof Error ? error.message : 'Unknown error');
      logger?.error({ error }, 'Failed');
      return rsp;
    }
  }
}
```

### Key Points

- Always implement `FunctionHandler` interface
- Use `to(req)` to initialize response from request
- Wrap in try/catch for error handling
- Use `normal()` for success, `fatal()` for errors
- Log with structured data using pino logger

---

## Pattern 2: Resource Extraction

**When to use**: Accessing composite resource data

### Extracting XR Data

```typescript
// Get observed (current) composite resource
const oxr = getObservedCompositeResource(req);

// Get desired composite resource
const dxr = getDesiredCompositeResource(req);

// Safe access to metadata
const name = oxr?.resource?.metadata?.name ?? 'unnamed';
const namespace = oxr?.resource?.metadata?.namespace ?? 'default';
const labels = oxr?.resource?.metadata?.labels ?? {};
const annotations = oxr?.resource?.metadata?.annotations ?? {};

// Safe access to spec with type assertion
interface MySpec {
  region: string;
  size?: 'small' | 'medium' | 'large';
  enableMonitoring?: boolean;
  tags?: Record<string, string>;
}

const spec = oxr?.resource?.spec as MySpec;
const region = spec?.region ?? 'us-west-2';
const size = spec?.size ?? 'small';
const enableMonitoring = spec?.enableMonitoring ?? false;
const tags = spec?.tags ?? {};
```

### Extracting Composed Resources

```typescript
// Get all desired composed resources (Map)
const desired = getDesiredComposedResources(req);

// Get all observed composed resources (Map)
const observed = getObservedComposedResources(req);

// Access specific composed resource
const myBucket = desired['bucket-main'];
const bucketStatus = observed['bucket-main']?.resource?.status;

// Check if resource exists
if (observed['bucket-main']) {
  const bucketArn = observed['bucket-main']?.resource?.status?.atProvider?.arn;
}
```

---

## Pattern 3: Composed Resource Creation

**When to use**: Adding resources to the composition

### Basic Resource Creation

```typescript
// Add a single resource
desired['bucket-main'] = {
  resource: {
    apiVersion: 'aws.m.upbound.io/v1beta1',
    kind: 'Bucket',
    metadata: {
      name: `bucket-${resourceName}`,
      labels: {
        'app.kubernetes.io/name': resourceName,
        'app.kubernetes.io/managed-by': 'crossplane'
      }
    },
    spec: {
      forProvider: {
        region: region,
        tags: {
          Name: `bucket-${resourceName}`,
          Environment: 'production',
          ...tags
        }
      }
    }
  }
};
```

### Resource with Cross-References

```typescript
// VPC resource
desired['vpc'] = {
  resource: {
    apiVersion: 'aws.m.upbound.io/v1beta1',
    kind: 'VPC',
    metadata: { name: `vpc-${resourceName}` },
    spec: {
      forProvider: {
        region: region,
        cidrBlock: '10.0.0.0/16',
        enableDnsHostnames: true
      }
    }
  }
};

// Subnet referencing VPC
desired['subnet-public'] = {
  resource: {
    apiVersion: 'aws.m.upbound.io/v1beta1',
    kind: 'Subnet',
    metadata: { name: `subnet-${resourceName}-public` },
    spec: {
      forProvider: {
        region: region,
        cidrBlock: '10.0.1.0/24',
        // Reference VPC using selector
        vpcIdSelector: {
          matchControllerRef: true  // Same composite resource
        }
      }
    }
  }
};
```

---

## Pattern 4: Conditional Resource Creation

**When to use**: Optional features or resources

### Simple Conditional

```typescript
const enableMonitoring = spec?.enableMonitoring ?? false;

if (enableMonitoring) {
  desired['cloudwatch-alarm'] = {
    resource: {
      apiVersion: 'aws.m.upbound.io/v1beta1',
      kind: 'MetricAlarm',
      metadata: { name: `alarm-${resourceName}` },
      spec: {
        forProvider: {
          region: region,
          alarmName: `${resourceName}-cpu-alarm`,
          comparisonOperator: 'GreaterThanThreshold',
          evaluationPeriods: 2,
          metricName: 'CPUUtilization',
          namespace: 'AWS/EC2',
          period: 300,
          statistic: 'Average',
          threshold: 80
        }
      }
    }
  };
}
```

### Multiple Conditions

```typescript
const enablePublicAccess = spec?.enablePublicAccess ?? false;
const enableEncryption = spec?.enableEncryption ?? true;

// Only create public access block if NOT enabling public access
if (!enablePublicAccess) {
  desired['bucket-public-access-block'] = {
    resource: {
      apiVersion: 'aws.m.upbound.io/v1beta1',
      kind: 'BucketPublicAccessBlock',
      metadata: { name: `pab-${resourceName}` },
      spec: {
        forProvider: {
          region: region,
          bucketSelector: { matchControllerRef: true },
          blockPublicAcls: true,
          blockPublicPolicy: true,
          ignorePublicAcls: true,
          restrictPublicBuckets: true
        }
      }
    }
  };
}

// Encryption configuration
if (enableEncryption) {
  desired['bucket-encryption'] = {
    resource: {
      apiVersion: 'aws.m.upbound.io/v1beta1',
      kind: 'BucketServerSideEncryptionConfiguration',
      metadata: { name: `enc-${resourceName}` },
      spec: {
        forProvider: {
          region: region,
          bucketSelector: { matchControllerRef: true },
          rule: [{
            applyServerSideEncryptionByDefault: [{
              sseAlgorithm: 'aws:kms'
            }]
          }]
        }
      }
    }
  };
}
```

---

## Pattern 5: Multiple Resources (Loops)

**When to use**: Creating multiple similar resources

### Array Iteration

```typescript
const subnets = spec?.subnets ?? [];
const zones = spec?.availabilityZones ?? ['us-west-2a', 'us-west-2b'];

// Create subnet for each CIDR
subnets.forEach((cidr, index) => {
  const zone = zones[index % zones.length];  // Round-robin zones

  desired[`subnet-${index}`] = {
    resource: {
      apiVersion: 'aws.m.upbound.io/v1beta1',
      kind: 'Subnet',
      metadata: {
        name: `subnet-${resourceName}-${index}`,
        labels: {
          'zone': zone,
          'index': String(index)
        }
      },
      spec: {
        forProvider: {
          region: region,
          availabilityZone: zone,
          cidrBlock: cidr,
          vpcIdSelector: { matchControllerRef: true },
          tags: {
            Name: `subnet-${resourceName}-${zone}`,
            Zone: zone
          }
        }
      }
    }
  };
});
```

### Security Group Rules

```typescript
interface SecurityRule {
  port: number;
  protocol: string;
  cidrBlocks: string[];
  description?: string;
}

const ingressRules: SecurityRule[] = spec?.ingressRules ?? [
  { port: 443, protocol: 'tcp', cidrBlocks: ['0.0.0.0/0'], description: 'HTTPS' },
  { port: 80, protocol: 'tcp', cidrBlocks: ['0.0.0.0/0'], description: 'HTTP' }
];

ingressRules.forEach((rule, index) => {
  desired[`sg-rule-ingress-${index}`] = {
    resource: {
      apiVersion: 'aws.m.upbound.io/v1beta1',
      kind: 'SecurityGroupRule',
      metadata: { name: `sgr-${resourceName}-in-${index}` },
      spec: {
        forProvider: {
          region: region,
          type: 'ingress',
          fromPort: rule.port,
          toPort: rule.port,
          protocol: rule.protocol,
          cidrBlocks: rule.cidrBlocks,
          description: rule.description ?? `Rule ${index}`,
          securityGroupIdSelector: { matchControllerRef: true }
        }
      }
    }
  };
});
```

---

## Pattern 6: Resource References (Selectors)

**When to use**: Linking resources together

### Three Types of Selectors

#### 1. Controller Reference (Same XR)

```typescript
// References parent composite resource
const selector = {
  matchControllerRef: true
};

// Usage in spec
spec: {
  forProvider: {
    vpcIdSelector: { matchControllerRef: true }
  }
}
```

#### 2. Label Matching

```typescript
// Reference resources by labels
const selector = {
  matchLabels: {
    'resource-type': 'storage',
    'tier': 'primary'
  }
};

// Usage
spec: {
  forProvider: {
    subnetIdSelector: {
      matchLabels: {
        'zone': 'us-west-2a',
        'type': 'private'
      }
    }
  }
}
```

#### 3. Combined (Controller + Labels)

```typescript
// Narrow selection within same XR
const selector = {
  matchControllerRef: true,
  matchLabels: {
    'tier': 'primary'
  }
};
```

### Full Example: RDS with Subnet Group

```typescript
// Create subnets with labels
zones.forEach((zone, index) => {
  desired[`subnet-db-${index}`] = {
    resource: {
      apiVersion: 'aws.m.upbound.io/v1beta1',
      kind: 'Subnet',
      metadata: {
        name: `subnet-db-${resourceName}-${index}`,
        labels: {
          'type': 'database',
          'zone': zone
        }
      },
      spec: {
        forProvider: {
          region: region,
          availabilityZone: zone,
          cidrBlock: dbSubnets[index],
          vpcIdSelector: { matchControllerRef: true }
        }
      }
    }
  };
});

// Subnet group references subnets by label
desired['db-subnet-group'] = {
  resource: {
    apiVersion: 'aws.m.upbound.io/v1beta1',
    kind: 'SubnetGroup',
    metadata: { name: `dbsg-${resourceName}` },
    spec: {
      forProvider: {
        region: region,
        description: 'Database subnet group',
        subnetIdSelector: {
          matchControllerRef: true,
          matchLabels: {
            'type': 'database'
          }
        }
      }
    }
  }
};
```

---

## Pattern 7: Type Safety

**When to use**: Ensuring compile-time safety

### Define Interfaces

```typescript
// XR Spec interface
interface DatabaseSpec {
  region: string;
  engine: 'postgres' | 'mysql' | 'mariadb';
  engineVersion?: string;
  instanceClass?: string;
  allocatedStorage?: number;
  multiAZ?: boolean;
  publiclyAccessible?: boolean;
  tags?: Record<string, string>;
}

// XR Status interface
interface DatabaseStatus {
  endpoint?: string;
  port?: number;
  state?: string;
}

// Internal configuration object
interface Config {
  resourceName: string;
  region: string;
  engine: string;
  engineVersion: string;
  instanceClass: string;
  allocatedStorage: number;
  multiAZ: boolean;
  publiclyAccessible: boolean;
  tags: Record<string, string>;
}

// Usage
const spec = oxr?.resource?.spec as DatabaseSpec;

const config: Config = {
  resourceName: oxr?.resource?.metadata?.name ?? 'db',
  region: spec?.region ?? 'us-west-2',
  engine: spec?.engine ?? 'postgres',
  engineVersion: spec?.engineVersion ?? '15.4',
  instanceClass: spec?.instanceClass ?? 'db.t3.micro',
  allocatedStorage: spec?.allocatedStorage ?? 20,
  multiAZ: spec?.multiAZ ?? false,
  publiclyAccessible: spec?.publiclyAccessible ?? false,
  tags: spec?.tags ?? {}
};
```

### Helper Functions with Types

```typescript
// Type-safe helper for creating metadata
function createMetadata(
  name: string,
  labels?: Record<string, string>
): { name: string; labels?: Record<string, string> } {
  return {
    name,
    ...(labels && { labels })
  };
}

// Usage
const metadata = createMetadata(`bucket-${resourceName}`, { env: 'prod' });
```

> There is deliberately no `createDefaultSpec()` helper. In Crossplane v2 a managed resource's
> `spec` is just `forProvider` — `managementPolicies` defaults to `['*']`, the XR's namespace is
> propagated automatically, and `providerConfigRef` defaults to
> `{ kind: 'ClusterProviderConfig', name: 'default' }`. Writing
> `providerConfigRef: { kind: 'ProviderConfig', name: 'default' }` points at a namespaced
> ProviderConfig that no template, example, or generated E2E test creates: the resource then gets
> no status conditions and no events at all, while composition tests still pass.

---

## Pattern 8: Error Handling

**When to use**: Robust error management

### Comprehensive Error Handling

```typescript
export class Function implements FunctionHandler {
  async RunFunction(
    req: RunFunctionRequest,
    logger?: Logger
  ): Promise<RunFunctionResponse> {
    const start = Date.now();

    try {
      let rsp = to(req);

      const oxr = getObservedCompositeResource(req);
      if (!oxr?.resource) {
        fatal(rsp, 'Missing observed composite resource');
        return rsp;
      }

      const spec = oxr.resource.spec as MySpec;

      // Validate required fields
      if (!spec?.region) {
        fatal(rsp, 'spec.region is required');
        return rsp;
      }

      const desired = getDesiredComposedResources(req);

      // Generate resources...

      rsp = setDesiredComposedResources(rsp, desired);
      normal(rsp, `Created ${Object.keys(desired).length} resources`);

      logger?.info({
        duration: Date.now() - start,
        resourceCount: Object.keys(desired).length
      }, 'Function completed successfully');

      return rsp;

    } catch (error) {
      const rsp = to(req);
      const errorMessage = error instanceof Error
        ? error.message
        : 'An unexpected error occurred';

      fatal(rsp, errorMessage);

      logger?.error({
        error: error instanceof Error ? {
          message: error.message,
          stack: error.stack
        } : error,
        duration: Date.now() - start
      }, 'Function failed');

      return rsp;
    }
  }
}
```

### Validation Helpers

```typescript
function validateSpec(spec: unknown): spec is MySpec {
  if (!spec || typeof spec !== 'object') return false;
  const s = spec as Record<string, unknown>;
  return typeof s.region === 'string';
}

// Usage
if (!validateSpec(oxr?.resource?.spec)) {
  fatal(rsp, 'Invalid spec: region is required');
  return rsp;
}
```

---

## Pattern 9: Logging

**When to use**: Debugging and observability

### Structured Logging with Pino

```typescript
export class Function implements FunctionHandler {
  async RunFunction(
    req: RunFunctionRequest,
    logger?: Logger
  ): Promise<RunFunctionResponse> {
    // Log function start
    logger?.debug({ request: req }, 'Function invoked');

    const oxr = getObservedCompositeResource(req);
    const resourceName = oxr?.resource?.metadata?.name;

    // Log with context
    logger?.info({ resourceName }, 'Processing composite resource');

    const desired = getDesiredComposedResources(req);

    // Log resource creation
    Object.keys(desired).forEach(key => {
      logger?.debug({
        resourceKey: key,
        kind: desired[key]?.resource?.kind
      }, 'Adding composed resource');
    });

    // Log completion with metrics
    logger?.info({
      resourceName,
      composedResourceCount: Object.keys(desired).length,
      resourceKeys: Object.keys(desired)
    }, 'Function completed');

    // ... rest of implementation
  }
}
```

### Log Levels

```typescript
logger?.debug(data, 'Detailed debugging info');
logger?.info(data, 'Normal operation info');
logger?.warn(data, 'Warning conditions');
logger?.error(data, 'Error conditions');
```

---

## Pattern 10: Default Values

**When to use**: Safe parameter access

### Nullish Coalescing and Optional Chaining

```typescript
// Safe access with defaults
const region = spec?.region ?? 'us-west-2';
const size = spec?.size ?? 'small';
const enableFeature = spec?.enableFeature ?? false;
const tags = spec?.tags ?? {};
const items = spec?.items ?? [];

// Nested safe access
const nestedValue = spec?.nested?.deeply?.value ?? 'default';

// Conditional property spread
const metadata = {
  name: resourceName,
  ...(spec?.labels && { labels: spec.labels }),
  ...(spec?.annotations && { annotations: spec.annotations })
};
```

### Size Mapping

```typescript
const sizeToInstanceClass: Record<string, string> = {
  small: 'db.t3.micro',
  medium: 'db.t3.small',
  large: 'db.t3.medium'
};

const size = spec?.size ?? 'small';
const instanceClass = sizeToInstanceClass[size] ?? sizeToInstanceClass.small;
```

### Computed Defaults

```typescript
// Default based on other values
const multiAZ = spec?.multiAZ ?? (spec?.environment === 'production');

// Default with computation
const allocatedStorage = spec?.allocatedStorage ??
  (spec?.size === 'large' ? 100 : spec?.size === 'medium' ? 50 : 20);
```

---


## Common Pitfalls Reference

### Pitfall 1: Forgetting npm install/build

**Problem**: Build fails with "dist directory not found"

**Solution**:
```bash
cd functions/<function-name>
npm install
npm run build
```

### Pitfall 2: Adding "Crossplane v2 required fields" that v2 already supplies

Remove `providerConfigRef`, `managementPolicies` and managed-resource `metadata.namespace`
unless the project's spec or API sets them — Crossplane v2 supplies all three by default.
`kind: 'ProviderConfig'` selects a namespaced ProviderConfig; when no `ProviderConfig` of that
name exists in the XR's namespace, the resource gets no status conditions at all while
composition tests still pass. See
[`control-plane-project-charter` §5](../../SKILL.md#5-crossplane-v2-what-a-composed-resource-actually-needs).

```typescript
spec: {
  forProvider: { ... }   // this is all you own
}
```

### Pitfall 3: Wrong API Version

**Problem**: Resources not found or wrong type

**Solution**:
```typescript
// CORRECT - namespaced
apiVersion: 'aws.m.upbound.io/v1beta1'

// WRONG - cluster-scoped
apiVersion: 'aws.upbound.io/v1beta1'
```

### Pitfall 4: Missing Resource Key

**Problem**: Resources overwrite each other

**Solution**:
```typescript
// Each resource needs unique key
desired['bucket-main'] = { ... };
desired['bucket-logs'] = { ... };  // Different key!

// For loops, use index
items.forEach((item, i) => {
  desired[`item-${i}`] = { ... };  // Unique key per item
});
```

### Pitfall 5: Unsafe Null Access

**Problem**: Runtime errors on undefined

**Solution**:
```typescript
// WRONG
const name = oxr.resource.metadata.name;

// CORRECT
const name = oxr?.resource?.metadata?.name ?? 'default';
```

### Pitfall 6: Not Returning Response

**Problem**: Function hangs or fails

**Solution**:
```typescript
// Always return response, even on error
try {
  // ... implementation
  return rsp;
} catch (error) {
  const rsp = to(req);
  fatal(rsp, error.message);
  return rsp;  // MUST return!
}
```

---

## Complete Example: S3 Bucket with Versioning

```typescript
import {
  FunctionHandler,
  RunFunctionRequest,
  RunFunctionResponse,
  getObservedCompositeResource,
  getDesiredComposedResources,
  setDesiredComposedResources,
  to,
  normal,
  fatal,
  Logger
} from '@crossplane-org/function-sdk-typescript';

interface BucketSpec {
  region: string;
  enableVersioning?: boolean;
  enableEncryption?: boolean;
  blockPublicAccess?: boolean;
  tags?: Record<string, string>;
}

export class Function implements FunctionHandler {
  async RunFunction(
    req: RunFunctionRequest,
    logger?: Logger
  ): Promise<RunFunctionResponse> {
    try {
      let rsp = to(req);
      const oxr = getObservedCompositeResource(req);
      const desired = getDesiredComposedResources(req);

      const spec = oxr?.resource?.spec as BucketSpec;
      const name = oxr?.resource?.metadata?.name ?? 'bucket';
      const region = spec?.region ?? 'us-west-2';
      const enableVersioning = spec?.enableVersioning ?? true;
      const enableEncryption = spec?.enableEncryption ?? true;
      const blockPublicAccess = spec?.blockPublicAccess ?? true;
      const tags = spec?.tags ?? {};


      // Main bucket
      desired['bucket'] = {
        resource: {
          apiVersion: 'aws.m.upbound.io/v1beta1',
          kind: 'Bucket',
          metadata: { name: `bucket-${name}` },
          spec: {
            forProvider: {
              region,
              tags: { Name: `bucket-${name}`, ...tags }
            }
          }
        }
      };

      // Versioning (conditional)
      if (enableVersioning) {
        desired['bucket-versioning'] = {
          resource: {
            apiVersion: 'aws.m.upbound.io/v1beta1',
            kind: 'BucketVersioning',
            metadata: { name: `versioning-${name}` },
            spec: {
              forProvider: {
                region,
                bucketSelector: { matchControllerRef: true },
                versioningConfiguration: [{ status: 'Enabled' }]
              }
            }
          }
        };
      }

      // Encryption (conditional)
      if (enableEncryption) {
        desired['bucket-encryption'] = {
          resource: {
            apiVersion: 'aws.m.upbound.io/v1beta1',
            kind: 'BucketServerSideEncryptionConfiguration',
            metadata: { name: `encryption-${name}` },
            spec: {
              forProvider: {
                region,
                bucketSelector: { matchControllerRef: true },
                rule: [{
                  applyServerSideEncryptionByDefault: [{
                    sseAlgorithm: 'aws:kms'
                  }]
                }]
              }
            }
          }
        };
      }

      // Public access block (conditional)
      if (blockPublicAccess) {
        desired['bucket-public-access-block'] = {
          resource: {
            apiVersion: 'aws.m.upbound.io/v1beta1',
            kind: 'BucketPublicAccessBlock',
            metadata: { name: `pab-${name}` },
            spec: {
              forProvider: {
                region,
                bucketSelector: { matchControllerRef: true },
                blockPublicAcls: true,
                blockPublicPolicy: true,
                ignorePublicAcls: true,
                restrictPublicBuckets: true
              }
            }
          }
        };
      }

      rsp = setDesiredComposedResources(rsp, desired);
      normal(rsp, `Created bucket ${name} with ${Object.keys(desired).length} resources`);

      logger?.info({ name, resourceCount: Object.keys(desired).length }, 'Success');
      return rsp;

    } catch (error) {
      const rsp = to(req);
      fatal(rsp, error instanceof Error ? error.message : 'Unknown error');
      logger?.error({ error }, 'Failed');
      return rsp;
    }
  }
}
```

---

---

# Part 4 — Build and test

## Workflow

### Prerequisites

```bash
# Generate function scaffold (if new)
up function generate my-function --language typescript

# Navigate to function directory
cd functions/my-function
```

### Build Steps

```bash
# 1. Install dependencies
npm install

# 2. Compile TypeScript
npm run build

# 3. Verify dist/ exists
ls -la dist/
```

### Test Steps

```bash
# Return to project root
cd ../..

# Run composition tests (test-* only: tests/* also runs the e2e programs)
up test run "tests/test-*"

# Build project container
up project build
```

### Common Build Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| `dist directory not found` | TypeScript not compiled | Run `npm run build` |
| `node_modules not found` | Dependencies not installed | Run `npm install` |
| TypeScript errors | Code issues | Fix errors shown by `npm run build` |
| Import errors | Wrong module paths | Check `tsconfig.json` moduleResolution |


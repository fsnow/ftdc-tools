# FTDC Parser Testing Coverage

## Current Test Coverage Status

### ⚠️ LIMITED - Requires Expansion

Currently tested with:
- **Single source**: MongoDB Atlas M0 cluster (Nov 2025)
- **Unknown version**: Likely MongoDB 7.0 or 8.0 (Atlas default)
- **Unknown platform**: Likely Linux ARM64 (Graviton) or x86_64
- **Environment**: Atlas-managed, no custom configurations

**This is insufficient for production use.**

---

## Required Test Coverage

### MongoDB Versions

We need FTDC samples from all currently supported MongoDB versions:

#### Community Server
- [ ] MongoDB 7.0.x (latest minor version)
- [ ] MongoDB 8.0.x (latest minor version)
- [ ] MongoDB 8.2.x (latest rapid release, if available)

#### Enterprise Server
- [ ] MongoDB 7.0.x Enterprise
- [ ] MongoDB 8.0.x Enterprise
- [ ] MongoDB 8.2.x Enterprise (if available)

**Why**: FTDC format may have version-specific changes or enterprise-only metrics.

---

### Platform Coverage

#### Operating Systems
- [ ] **Linux x86_64** (Ubuntu 22.04, RHEL 8, RHEL 9)
- [ ] **Linux ARM64** (Ubuntu 22.04 ARM, Amazon Linux 2 Graviton)
- [ ] **macOS x86_64** (Intel Mac)
- [ ] **macOS ARM64** (Apple Silicon - M1/M2/M3)
- [ ] **Windows x86_64** (Windows Server 2022)

**Why**: Platform-specific metrics (CPU, memory, disk) may affect FTDC structure.

---

### Deployment Types

#### Standalone
- [ ] Single mongod instance
- [ ] Default configuration
- [ ] Custom configuration (non-default storage engine options)

#### Replica Sets
- [ ] 3-node replica set (PSS)
- [ ] 5-node replica set
- [ ] Replica set with arbiter
- [ ] Replica set with hidden members

#### Sharded Clusters
- [ ] Config server replica set
- [ ] Shard replica set
- [ ] mongos router

#### MongoDB Atlas
- [ ] M0 (Free tier) - **CURRENT**
- [ ] M10 (Shared)
- [ ] M30 (Dedicated)
- [ ] Serverless

**Why**: Different topologies may have different metrics sets.

---

### Special Configurations

#### Storage Engines
- [ ] WiredTiger (default)
- [ ] In-Memory (Enterprise)

#### Security
- [ ] No authentication
- [ ] SCRAM-SHA-256 authentication
- [ ] x.509 authentication
- [ ] LDAP authentication (Enterprise)
- [ ] Encryption at rest (Enterprise)

#### Features
- [ ] Audit logging enabled (Enterprise)
- [ ] Time-series collections
- [ ] Sharding enabled
- [ ] Change streams active
- [ ] Transactions in use

**Why**: Feature-specific metrics may be present or absent.

---

## Known Test Files

### Current Inventory

| Source | Version | Platform | Type | Size | Status |
|--------|---------|----------|------|------|--------|
| Atlas M0 | Unknown | Unknown (likely ARM64) | RS Member | 1.5MB | ⚠️ Python parser fails |
| Atlas M0 Interim | Unknown | Unknown (likely ARM64) | RS Member | 44KB | ❌ Known parsing issues |

---

## Test Acquisition Plan

### Phase 1: Version Coverage (HIGH PRIORITY)

**Goal**: Get FTDC from all supported MongoDB versions

**Tasks**:
1. [ ] Spin up MongoDB 7.0.x locally (Docker)
   ```bash
   docker run -d --name mongo70 -p 27017:27017 mongo:7.0
   # Let run for 5-10 minutes to generate FTDC
   docker cp mongo70:/data/db/diagnostic.data/ ./test-data/mongo-7.0-linux-x86_64/
   ```

2. [ ] Spin up MongoDB 8.0.x locally (Docker)
   ```bash
   docker run -d --name mongo80 -p 27017:27017 mongo:8.0
   docker cp mongo80:/data/db/diagnostic.data/ ./test-data/mongo-8.0-linux-x86_64/
   ```

3. [ ] Spin up MongoDB 8.2.x locally (Docker, if available)

4. [ ] Document version for each FTDC file
   ```bash
   # Check MongoDB version
   docker exec mongo70 mongosh --eval "db.version()"
   ```

### Phase 2: Platform Coverage (MEDIUM PRIORITY)

**Goal**: Get FTDC from different platforms

**Tasks**:
1. [ ] Linux ARM64 (Graviton)
   - Use AWS EC2 t4g instance or Docker on ARM Mac

2. [ ] macOS ARM64 (Apple Silicon)
   - Install MongoDB locally on M1/M2/M3 Mac
   - Or use user's Mac if available

3. [ ] Windows
   - Use Windows VM or WSL2

4. [ ] Document platform for each file
   ```bash
   uname -a > platform-info.txt
   ```

### Phase 3: Topology Coverage (LOW PRIORITY)

**Goal**: Get FTDC from different deployment types

**Tasks**:
1. [ ] Set up 3-node replica set locally
2. [ ] Set up basic sharded cluster
3. [ ] Collect FTDC from config servers, shards, mongos

---

## Test Data Repository Structure

Proposed structure for test FTDC files:

```
ftdc-tools/
└── test-data/           # NOT committed to git (in .gitignore)
    ├── README.md        # Instructions and metadata
    ├── mongodb-7.0/
    │   ├── linux-x86_64/
    │   │   ├── standalone/
    │   │   │   └── metrics.2025-11-14T...
    │   │   └── replica-set/
    │   │       └── metrics.2025-11-14T...
    │   ├── linux-arm64/
    │   ├── macos-arm64/
    │   └── windows-x86_64/
    ├── mongodb-8.0/
    │   └── [same structure]
    └── mongodb-8.2/
        └── [same structure]
```

**Note**: Test data files should NOT be committed to git due to size and potential sensitivity.

---

## Continuous Integration Testing

### Test Matrix for CI/CD

Update `.github/workflows/ci.yml` to test against multiple FTDC files:

```yaml
strategy:
  matrix:
    mongodb-version: ['7.0', '8.0', '8.2']
    platform: ['linux-x86_64', 'linux-arm64']

steps:
  - name: Download test FTDC
    run: |
      # Download from S3 or test data repository
      wget https://ftdc-test-data.s3.amazonaws.com/mongo-${{ matrix.mongodb-version }}-${{ matrix.platform }}.tar.gz

  - name: Test Python parser
    run: |
      pytest tests/ --ftdc-path=test-data/

  - name: Test Go CLI
    run: |
      ./go/bin/ftdc-cli extract test-data/*.ftdc
```

---

## Test Coverage Checklist

Before declaring production-ready:

### Minimum Required Coverage
- [ ] MongoDB 7.0 (Linux x86_64)
- [ ] MongoDB 8.0 (Linux x86_64)
- [ ] At least one ARM64 platform
- [ ] Replica set topology
- [ ] Both Python parser and Go CLI tested

### Recommended Coverage
- [ ] All supported MongoDB versions
- [ ] All major platforms (Linux, macOS, Windows)
- [ ] All deployment types (standalone, RS, sharded)
- [ ] Both community and enterprise editions

### Gold Standard Coverage
- [ ] Complete matrix (all versions × all platforms)
- [ ] Special configurations (encryption, audit, etc.)
- [ ] Stress testing with very large FTDC files (>100MB)
- [ ] Performance benchmarking across versions

---

## Current Blockers

### Critical Issues
1. ⚠️ **Version Unknown**: Current Atlas FTDC version not documented
2. ⚠️ **Platform Unknown**: Current Atlas platform not documented
3. 🔴 **Python Parser Broken**: Fails on current test data
4. ⚠️ **Single Data Source**: Only one FTDC source tested

### Next Steps
1. Document current Atlas FTDC version and platform
2. Fix Python parser double precision bug
3. Acquire FTDC from MongoDB 7.0 and 8.0
4. Set up CI testing with multiple FTDC files

---

**Last Updated**: 2025-11-14
**Status**: ⚠️ INSUFFICIENT - Expansion Required

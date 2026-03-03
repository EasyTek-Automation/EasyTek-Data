# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is the Node-RED component of the AMG_Data platform. It handles industrial data ingestion from energy meters (PAC3100) via Modbus TCP, processing, and persistence to MongoDB. It runs inside Docker and is part of the broader AMG_Data IoT stack.

## Running Node-RED

```bash
# Via Docker (production)
docker build -t amg-node-red .
docker run -p 1880:1880 amg-node-red

# The editor is available at http://localhost:1880 (port set by PORT env var)
# Admin credentials are defined in settings.js → adminAuth
```

There is no local dev runner outside Docker. To test flows locally, install Node-RED globally:
```bash
npm install -g node-red
cd node-red
node-red --settings settings.js
```

## Architecture

### Flows (`flows.json`)

Three tabs exist:

| Tab | Status | Purpose |
|-----|--------|---------|
| **Fluxo 1** | Disabled | Legacy individual Modbus getters (experimental, not in use) |
| **Telemetria SE03** | **Active** | Main production flow: SE03 substation live telemetry |
| **PAC3100 Scanner (Exemplo)** | Active | Reference/example flow for PAC3100 scan sequence |

### Telemetria SE03 — Main Flow

Reads 7 PAC3100 energy meters (MM01–MM07) via a single Modbus TCP connection to a RS485-to-TCP converter (`192.168.1.10:8899`). Key subsystems:

- **Scheduler** (`Varredura 2min`): Inject node triggering scans every 2 minutes. Uses a `busy` flag to prevent overlapping reads.
- **PAC3100 Flex**: `modbus-flex-getter` node that reads registers sequentially per meter.
- **Decode stage**: Function nodes decode raw Modbus buffers:
  - Voltages/currents: 2 registers → 32-bit Big-Endian float (`buf.readFloatBE(0)`)
  - Energy (Wh): 4 registers → 64-bit Double BE
  - Demand period counters: 4 registers → U32 BE (seconds)
- **Filtro MM0x nodes**: Route decoded data per meter (`AllData_MM0x` → individual field filters)
- **Watchdog** (`Watchdog 1 s`): Inject node running every 1s. If >8s without new data, triggers a reconnection shot.
- **Consumption Gate** (`Gate Consumo ≥15min?`): Only writes energy/consumption records to MongoDB when ≥15 minutes have passed since last write.
- **MaxMin tracking** (`S03_MM0xMax` / `S03_MM0xMin`): Stores per-meter peak demand values.
- **MongoDB writes**: `mongodb4` nodes persist data to the `Cluster-EasyTek` database at `host.docker.internal:27017`.

### External Connections

| Resource | Address | Notes |
|----------|---------|-------|
| Modbus TCP | `192.168.1.10:8899` | RS485-to-TCP converter → PAC3100 meters |
| MongoDB | `host.docker.internal:27017` | Database: `Cluster-EasyTek` |

### Global Context

- `moment` (moment-timezone): Available globally via `global.get('moment')` in all Function nodes (declared in `settings.js → functionGlobalContext`)

### Installed Nodes (from `package.json` / `.config.nodes.json`)

- `node-red-contrib-modbus` 5.43.0 — Modbus TCP/RTU
- `node-red-contrib-mongodb4` 3.1.1 — MongoDB operations

## Key Files

| File | Purpose |
|------|---------|
| `flows.json` | All Node-RED flows (pretty-printed JSON, git-friendly) |
| `flows_cred.json` | Encrypted node credentials (do not edit manually) |
| `settings.js` | Runtime config: port, auth, logging, global context |
| `Dockerfile` | Docker image build (copies flows + settings into `/data`) |
| `config.json` | Fault/machine code lookup tables (generic equipment) |
| `configAreaDecapado.json` | Fault/machine code lookup tables (Decapado area specific) |

## Flow Development Conventions

- **Modbus reads**: Always use `modbus-flex-getter` (not `modbus-getter`) for the SE03 flow — it supports dynamic unit ID and register address via `msg.payload`, enabling a sequential scheduler pattern with a single client node.
- **Busy flag pattern**: Set `flow.set('busy', true)` before Modbus read, clear it in both success and error handlers (`Release Busy (OK)` and `Handle Error (ERR)` nodes). This prevents queue buildup.
- **Register decoding**: PAC3100 uses Big-Endian byte order. Float32 = 2 registers, `buf.readFloatBE(0)`. Double64 = 4 registers.
- **Timestamps**: Use `global.get('moment')()` for timezone-aware timestamps.
- **MongoDB collection names**: Match the collections used by the webapp (`AMG_EnergyData`, `AMG_Consumo`, etc.) — check `webapp/src/` callbacks for the exact names.

## Docker Deployment Notes

The Dockerfile copies `flows.json`, `flows_cred.json`, `settings.js`, and `package.json` into the container's `/data` directory, then runs `npm install`. The Node-RED base image entrypoint expects `WORKDIR /usr/src/node-red` — do not change the final `WORKDIR`.

To update flows in production: rebuild the Docker image after editing `flows.json`.

## Credential Secret

The `credentialSecret` in `settings.js` is commented out (uses auto-generated key). If `flows_cred.json` is regenerated on a new container, credentials stored in it (MQTT passwords, API keys in HTTP Request nodes) may be lost. Keep `flows_cred.json` in version control alongside the container instance.

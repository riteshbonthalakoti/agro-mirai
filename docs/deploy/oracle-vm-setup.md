# Oracle VM setup runbook (Module 21)

A runbook for Ritesh to follow himself once an Oracle Cloud account
exists (blocked on entering payment card details, per the project's
current scope note — nothing in this file was executed against a real
VM in this session). Covers provisioning, Docker, and the two Module 21
services (`services/cnn-inference`, `services/voice`).

## 1. Shape and region

- **Shape:** `VM.Standard.A1.Flex` (Ampere A1, aarch64) — Oracle's
  Always Free compute offering.
- **Current free allocation (verified via web search, June 2026):**
  Oracle silently cut the Always Free Ampere A1 allocation from
  4 OCPU/24GB to **2 OCPU/12GB** effective June 15, 2026, with no public
  announcement — confirmed by multiple independent sources (Oracle's own
  Cloud Customer Connect forum, InfoQ, community write-ups). Provision a
  single `VM.Standard.A1.Flex` instance with 2 OCPUs and 12GB memory —
  that is the full remaining free-tier budget; do not split it across
  two instances unless you have a specific reason to (this repo's
  `docker-compose.yml` assumes both services on one host).
- **Region:** pick whichever region your Oracle tenancy was created in
  that has A1 capacity available — A1 availability is capacity-
  constrained per region/AD and has historically had "out of capacity"
  errors on the free tier; if the first AD/region fails, try another AD
  in the same region before switching regions.
- **Verify current numbers yourself before provisioning** —
  `oci compute shape list --compartment-id <root-compartment-ocid>` (via
  the OCI CLI, installed per §2) or the Console's Always Free page, since
  this allocation has already changed once without notice and could
  again.

## 2. Provisioning (CLI-first, per this project's hard rule #1)

```bash
# Install/configure the OCI CLI first (interactive — needs your own
# tenancy OCID, user OCID, and API key fingerprint from the Console):
oci setup config

# Verify:
oci iam region list

# Create the instance (fill in your own compartment/subnet/AD OCIDs and
# an SSH public key path):
oci compute instance launch \
  --compartment-id <compartment-ocid> \
  --availability-domain <ad-name> \
  --shape VM.Standard.A1.Flex \
  --shape-config '{"ocpus": 2, "memoryInGBs": 12}' \
  --image-id <ubuntu-22.04-or-24.04-arm64-image-ocid> \
  --subnet-id <subnet-ocid> \
  --assign-public-ip true \
  --ssh-authorized-keys-file ~/.ssh/agro_mirai_oracle.pub \
  --display-name agro-mirai-inference
```

Find the current Ubuntu ARM64 image OCID for your region via
`oci compute image list --compartment-id <compartment-ocid> --operating-system "Canonical Ubuntu" --shape VM.Standard.A1.Flex`
— image OCIDs are region-specific and change over time, so don't hardcode
one here.

**SSH key handling:** generate a dedicated key pair for this VM
(`ssh-keygen -t ed25519 -f ~/.ssh/agro_mirai_oracle`), never reuse a key
already used elsewhere. The private key stays on Ritesh's machine only —
never committed to this repo (already covered by the root `.gitignore`'s
`*.pem`/`id_*` patterns; double-check before any `git add` touching a
`.ssh/` path).

## 3. Firewall / security list — expose ONLY the two service ports

By default OCI's default security list only allows inbound SSH (22).
Add ingress rules for exactly the two ports this repo's
`docker-compose.yml` publishes — **not** a blanket 0.0.0.0/0-all-ports
rule:

- **TCP 8001** — `cnn-inference` (`services/cnn-inference`)
- **TCP 8002** — `voice` (`services/voice`)

Via CLI:

```bash
oci network security-list update --security-list-id <default-seclist-ocid> \
  --ingress-security-rules '[
    {"protocol":"6","source":"0.0.0.0/0","tcpOptions":{"destinationPortRange":{"min":22,"max":22}}},
    {"protocol":"6","source":"<render-egress-cidr-or-your-ip>","tcpOptions":{"destinationPortRange":{"min":8001,"max":8001}}},
    {"protocol":"6","source":"<render-egress-cidr-or-your-ip>","tcpOptions":{"destinationPortRange":{"min":8002,"max":8002}}}
  ]'
```

Prefer scoping the `source` CIDR to Render's known egress IPs (check
Render's dashboard/docs for the current list) rather than `0.0.0.0/0` —
these two services have no auth of their own today (a real, documented
gap; see the ADR's known limitations). Also open the equivalent ports in
Ubuntu's own `iptables`/`ufw` if enabled — OCI's security list is
necessary but not sufficient, the instance's own firewall is a second
layer that defaults to blocking on some Ubuntu cloud images.

## 4. Docker + Docker Compose (Ubuntu ARM64)

```bash
ssh -i ~/.ssh/agro_mirai_oracle ubuntu@<vm-public-ip>

sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

sudo usermod -aG docker $USER
# log out/in for the group change to take effect

docker compose version   # confirm the plugin installed (`docker compose`, not standalone docker-compose)
```

**Swap file (recommended, per docker-compose.yml's resource-math
caveat):** Ampere A1 free-tier instances have no swap by default. Given
the tight 8.5GB-of-12GB budget both services together need, add a swap
file as OOM insurance:

```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 5. Deploy this repo's two services

```bash
git clone https://github.com/riteshbonthalakoti/agro-mirai.git /opt/agro-mirai
cd /opt/agro-mirai
mkdir -p /opt/agro-mirai/models   # for the CNN artifact, see services/cnn-inference/README.md

# Copy the gitignored trained artifacts here first (from your machine):
#   scp models/disease_cnn_mobilenetv2.pt models/disease_cnn_class_names.json \
#       ubuntu@<vm-ip>:/opt/agro-mirai/models/

docker compose build
docker compose up -d
docker compose ps
curl http://localhost:8001/health
curl http://localhost:8002/health   # will show "degraded" until AI4Bharat's
                                     # first-run weight download finishes —
                                     # check docker compose logs voice
```

Then set `CNN_SERVICE_URL=http://<vm-public-ip>:8001` and
`VOICE_SERVICE_URL=http://<vm-public-ip>:8002` in Render's environment
variables for the main API (see `.env.example`/`render.yaml`).

## 6. What's verified vs. what needs Ritesh to confirm

**Verified in this session (no VM involved):** the Dockerfiles build
logically correct instructions; the app code (`services/cnn-inference`,
`services/voice`) is unit-tested with stub models; `docker-compose.yml`'s
resource numbers are a documented estimate, not a measurement.

**NOT verified — needs Ritesh, on the real VM, before trusting this:**
- The current Always Free 2 OCPU/12GB numbers, and actual A1 capacity
  availability in his chosen region/AD, at the time he actually
  provisions (Oracle has changed this once already without notice).
- Whether the pinned torch/torchvision wheels actually resolve on real
  aarch64 hardware (`services/cnn-inference/README.md`'s ARM64 section)
  — the biggest single technical risk in this whole module.
- Real `docker stats` memory/CPU usage under load, to check the resource
  math above isn't just optimistic.
- Whether Render's actual egress IP range can be scoped into the
  security list (§3), or whether `0.0.0.0/0` is the pragmatic fallback
  for a capstone-scale deployment.

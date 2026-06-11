# Step-by-step: install Apache YARN locally

Use this guide to run a **local YARN Resource Manager** so you can test [yarn-worker](./README.md). The worker needs:

- RM REST API: `http://<host>:8088/ws/v1/cluster/...`
- Log URLs from app details (`amContainerLogs`) reachable from your machine

Two paths are below. **Docker is faster** for a dev laptop; **tarball install** is closer to a real single-node cluster.

---

## Before you choose a path

| Requirement | Docker path | Tarball path |
|-------------|-------------|--------------|
| OS | Linux (or Linux VM) with Docker | Linux (Ubuntu/Debian recommended) |
| Java | Inside images | **OpenJDK 11** on host |
| RAM | ~4 GB free for containers | ~4 GB for Hadoop JVMs |
| Time | ~15 minutes | ~30–45 minutes |

After either path, set in yarn-worker `.env`:

```bash
YARN_RM_URL=http://127.0.0.1:8088
YARN_AUTH_TYPE=none
```

---

## Path A — YARN with Docker (recommended)

### Step 1 — Install Docker

**Ubuntu / Debian:**

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker "$USER"
```

Log out and back in (or `newgrp docker`) so your user can run Docker without `sudo`.

Verify:

```bash
docker --version
docker compose version
```

### Step 2 — Create a minimal Hadoop + YARN stack

Create a directory (anywhere; example `~/hadoop-yarn-dev`):

```bash
mkdir -p ~/hadoop-yarn-dev
cd ~/hadoop-yarn-dev
```

Create `hadoop.env`:

```bash
cat > hadoop.env <<'EOF'
CORE_CONF_fs_defaultFS=hdfs://namenode:9000
HDFS_CONF_dfs_replication=1
YARN_CONF_yarn_resourcemanager_hostname=resourcemanager
YARN_CONF_yarn_timeline-service_enabled=false
YARN_CONF_yarn_log___aggregation___enable=true
EOF
```

Create `docker-compose.yml`:

```bash
cat > docker-compose.yml <<'EOF'
services:
  namenode:
    image: bde2020/hadoop-namenode:2.0.0-hadoop3.2.1-java8
    container_name: namenode
    restart: always
    ports:
      - "9870:9870"
      - "9000:9000"
    env_file:
      - hadoop.env
    environment:
      - CLUSTER_NAME=dev
    volumes:
      - namenode_data:/hadoop/dfs/name

  datanode:
    image: bde2020/hadoop-datanode:2.0.0-hadoop3.2.1-java8
    container_name: datanode
    restart: always
    env_file:
      - hadoop.env
    environment:
      - SERVICE_PRECONDITION=namenode:9870
    volumes:
      - datanode_data:/hadoop/dfs/data

  resourcemanager:
    image: bde2020/hadoop-resourcemanager:2.0.0-hadoop3.2.1-java8
    container_name: resourcemanager
    restart: always
    ports:
      - "8088:8088"
    env_file:
      - hadoop.env
    environment:
      - SERVICE_PRECONDITION=namenode:9870 datanode:9864

  nodemanager:
    image: bde2020/hadoop-nodemanager:2.0.0-hadoop3.2.1-java8
    container_name: nodemanager
    restart: always
    env_file:
      - hadoop.env
    environment:
      - SERVICE_PRECONDITION=namenode:9870 datanode:9864 resourcemanager:8088

  historyserver:
    image: bde2020/hadoop-historyserver:2.0.0-hadoop3.2.1-java8
    container_name: historyserver
    restart: always
    env_file:
      - hadoop.env
    environment:
      - SERVICE_PRECONDITION=namenode:9870 datanode:9864 resourcemanager:8088

volumes:
  namenode_data:
  datanode_data:
EOF
```

### Step 3 — Start the cluster

```bash
cd ~/hadoop-yarn-dev
docker compose up -d
```

Wait until services are healthy (1–3 minutes):

```bash
docker compose ps
docker logs resourcemanager 2>&1 | tail -20
```

### Step 4 — Verify YARN is up

**RM UI:** open [http://127.0.0.1:8088/cluster](http://127.0.0.1:8088/cluster)

**REST API (same check yarn-worker uses):**

```bash
curl -s http://127.0.0.1:8088/ws/v1/cluster/info | head
curl -s "http://127.0.0.1:8088/ws/v1/cluster/apps?limit=5" | head
```

You should see JSON with cluster info / apps (apps may be empty at first).

### Step 5 — Submit a test job (so the worker has apps to list)

Enter the resource manager container and run a built-in MapReduce example:

```bash
docker exec -it resourcemanager bash
```

Inside the container:

```bash
yarn jar /opt/hadoop-3.2.1/share/hadoop/mapreduce/hadoop-mapreduce-examples-*.jar pi 2 5
exit
```

Refresh [http://127.0.0.1:8088/cluster/apps](http://127.0.0.1:8088/cluster/apps). Note the **application name** (often `QuasiMonteCarlo` for this example).

For yarn-worker tests with default `.env` (`YARN_APPLICATION_TYPES=SPARK`), either:

- Submit a **Spark** job to this YARN, or  
- Temporarily set `YARN_APPLICATION_TYPES=MAPREDUCE` (or leave types unset in tool `params`) when querying MapReduce examples.

### Step 6 — Point yarn-worker at local RM

In `yarn-worker/.env`:

```bash
YARN_RM_URL=http://127.0.0.1:8088
YARN_AUTH_TYPE=none
```

Test from the worker repo:

```bash
curl -s "http://127.0.0.1:8088/ws/v1/cluster/apps?applicationName=QuasiMonteCarlo&limit=3&sortBy=-startedTime"
```

### Step 7 — Stop / reset the cluster

```bash
cd ~/hadoop-yarn-dev
docker compose down      # stop
docker compose down -v   # stop and delete HDFS data volumes
```

---

## Path B — Single-node YARN on Linux (tarball)

### Step 1 — Install Java 11

**Ubuntu / Debian:**

```bash
sudo apt update
sudo apt install -y openjdk-11-jdk ssh pdsh
java -version
```

Set `JAVA_HOME` (adjust path if needed):

```bash
echo 'export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64' >> ~/.bashrc
echo 'export PATH=$JAVA_HOME/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

### Step 2 — SSH localhost (required by Hadoop scripts)

```bash
ssh-keygen -t rsa -P '' -f ~/.ssh/id_rsa
cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
ssh -o StrictHostKeyChecking=no localhost echo ok
```

### Step 3 — Download and unpack Hadoop

Use Hadoop **3.3.x** (stable; matches common RM API behavior):

```bash
cd ~
wget https://dlcdn.apache.org/hadoop/common/hadoop-3.3.6/hadoop-3.3.6.tar.gz
tar -xzf hadoop-3.3.6.tar.gz
mv hadoop-3.3.6 hadoop
```

```bash
echo 'export HADOOP_HOME=$HOME/hadoop' >> ~/.bashrc
echo 'export PATH=$HADOOP_HOME/bin:$HADOOP_HOME/sbin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

### Step 4 — Configure pseudo-distributed mode

Replace `$USER` below with your Linux username.

**`$HADOOP_HOME/etc/hadoop/core-site.xml`:**

```xml
<configuration>
  <property>
    <name>fs.defaultFS</name>
    <value>hdfs://localhost:9000</value>
  </property>
</configuration>
```

**`$HADOOP_HOME/etc/hadoop/hdfs-site.xml`:**

```xml
<configuration>
  <property>
    <name>dfs.replication</name>
    <value>1</value>
  </property>
  <property>
    <name>dfs.namenode.name.dir</name>
    <value>file:///home/USER/hadoop-data/nn</value>
  </property>
  <property>
    <name>dfs.datanode.data.dir</name>
    <value>file:///home/USER/hadoop-data/dn</value>
  </property>
</configuration>
```

**`$HADOOP_HOME/etc/hadoop/mapred-site.xml`:**

```xml
<configuration>
  <property>
    <name>mapreduce.framework.name</name>
    <value>yarn</value>
  </property>
</configuration>
```

**`$HADOOP_HOME/etc/hadoop/yarn-site.xml`:**

```xml
<configuration>
  <property>
    <name>yarn.nodemanager.aux-services</name>
    <value>mapreduce_shuffle</value>
  </property>
  <property>
    <name>yarn.nodemanager.env-whitelist</name>
    <value>JAVA_HOME,HADOOP_COMMON_HOME,HADOOP_HDFS_HOME,HADOOP_CONF_DIR,CLASSPATH_PREPEND_DISTCACHE,HADOOP_YARN_HOME,HADOOP_MAPRED_HOME</value>
  </property>
</configuration>
```

Create data dirs:

```bash
mkdir -p ~/hadoop-data/nn ~/hadoop-data/dn
```

### Step 5 — Format HDFS (once)

```bash
hdfs namenode -format
```

If asked to re-format, only do this on a **new** install (it wipes HDFS metadata).

### Step 6 — Start HDFS and YARN

```bash
start-dfs.sh
start-yarn.sh
```

Check Java processes:

```bash
jps
```

Expected: `NameNode`, `DataNode`, `ResourceManager`, `NodeManager`.

### Step 7 — Verify YARN

```bash
yarn node -list
curl -s http://127.0.0.1:8088/ws/v1/cluster/info
```

UI: [http://127.0.0.1:8088](http://127.0.0.1:8088)

### Step 8 — Submit a test application

```bash
yarn jar $HADOOP_HOME/share/hadoop/mapreduce/hadoop-mapreduce-examples-*.jar pi 2 5
```

Confirm in the RM UI under **Applications**.

### Step 9 — Configure yarn-worker

```bash
# yarn-worker/.env
YARN_RM_URL=http://127.0.0.1:8088
YARN_AUTH_TYPE=none
```

### Step 10 — Stop services

```bash
stop-yarn.sh
stop-dfs.sh
```

---

## Connect yarn-worker after YARN is running

1. Complete [LOCAL_DEVELOPMENT.md](./LOCAL_DEVELOPMENT.md) (Python venv, LiteLLM, `.env`).
2. Ensure `YARN_RM_URL` points at your RM (Docker or tarball: `http://127.0.0.1:8088`).
3. Run `langgraph dev` and ask for logs by **application name** that exists in the RM UI.
4. If you only have MapReduce test jobs, pass `applicationTypes` in the tool params or relax `YARN_APPLICATION_TYPES` in `.env`.

Example prompt:

```text
Get logs for application name QuasiMonteCarlo
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Connection refused` on 8088 | RM not started: `docker compose ps` or `jps` / `start-yarn.sh` |
| Namenode won’t start (Docker) | First boot takes time; check `docker logs namenode` |
| `localhost:8088` works but tool log fetch fails | NodeManager log links use container/hostnames; from Docker, run yarn-worker on same Docker network or use tarball install on host |
| No apps in API | Submit Step 5/8 example job; check `states` includes `FINISHED` |
| Worker filters out your app | Default `YARN_APPLICATION_TYPES=SPARK`; use Spark or change env / tool params |
| Port 8088 already in use | Another RM running; change compose port mapping or stop the other service |

---

## Production / company cluster

You usually **do not install** YARN locally—you use an existing RM URL from your platform team:

```bash
YARN_RM_URL=http://<production-rm-host>:8088
```

Use VPN or SSH tunnel if the RM is only reachable inside the corporate network. Set `YARN_AUTH_TYPE` to `basic` or `bearer` if your cluster requires it.

---

## Quick reference

| Service | URL |
|---------|-----|
| YARN ResourceManager UI | <http://127.0.0.1:8088> |
| RM REST API base | <http://127.0.0.1:8088/ws/v1/cluster> |
| HDFS NameNode UI (if installed) | <http://127.0.0.1:9870> |

Next: [LOCAL_DEVELOPMENT.md](./LOCAL_DEVELOPMENT.md) — install and run the LangGraph worker against this RM.

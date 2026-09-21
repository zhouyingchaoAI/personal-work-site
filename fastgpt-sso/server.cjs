const http = require('http');
const crypto = require('crypto');
const fs = require('fs');
const { MongoClient } = require('/app/node_modules/.pnpm/mongodb@6.20.0_gcp-metadata@5.3.0_socks@2.8.9/node_modules/mongodb');
const Redis = require('/app/node_modules/.pnpm/ioredis@5.6.0/node_modules/ioredis');

const mongo = new MongoClient(process.env.MONGODB_URI);
const redis = new Redis(process.env.REDIS_URL);
const secret = process.env.SSO_SECRET;
const kbBridgeSecret = process.env.FASTGPT_KB_BRIDGE_SECRET;

function personalApiDatasetToken(username) {
  return crypto.createHmac('sha256', kbBridgeSecret).update(`apidataset:personal:${username}`).digest('hex');
}

function fastgptRequest(token, path, payload) {
  return new Promise((resolve, reject) => {
    const raw = Buffer.from(JSON.stringify(payload || {}));
    const req = http.request({
      host: 'fastgpt-app', port: 3000, path, method: 'POST',
      headers: { 'content-type': 'application/json', 'content-length': raw.length, cookie: `fastgpt_token=${token}` }
    }, (res) => {
      let body = '';
      res.on('data', (part) => { body += part; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(body || '{}');
          if (res.statusCode >= 400 || Number(parsed.code || 200) >= 400) return reject(new Error(parsed.message || `FastGPT HTTP ${res.statusCode}`));
          resolve(parsed.data);
        } catch (error) { reject(error); }
      });
    });
    req.on('error', reject);
    req.write(raw);
    req.end();
  });
}

async function ensureDatasetPermission(resourceId, member) {
  await mongo.db('fastgpt').collection('resource_permissions').updateOne(
    { resourceId, resourceType: 'dataset', tmbId: member._id },
    { $set: { teamId: member.teamId, tmbId: member._id, resourceId, resourceType: 'dataset', permission: 4294967295 } },
    { upsert: true }
  );
}

async function ensureRagflowDatasets(user, member, token) {
  const db = mongo.db('fastgpt');
  const datasets = db.collection('datasets');
  // 企业库并非仅创建者私有：向每位办公成员单独授予权限，避免单一 FastGPT
  // team 的成员权限模型把它隐藏掉。
  const enterprise = await datasets.findOne({ name: '企业知识库（RAGFlow）', type: 'apiDataset', deleteTime: null });
  if (enterprise) await ensureDatasetPermission(enterprise._id, member);

  const name = '个人知识库（RAGFlow）';
  let personal = await datasets.findOne({ tmbId: member._id, name, type: 'apiDataset', deleteTime: null });
  if (!personal) {
    if (!enterprise) throw new Error('企业 RAGFlow 知识库模板尚未创建');
    personal = structuredClone(enterprise);
    delete personal._id;
    delete personal.__v;
    // structuredClone does not preserve BSON ObjectId prototypes. Keep the
    // actual member/team ObjectId so FastGPT's String(dataset.teamId) check
    // continues to match the authenticated team.
    personal.teamId = member.teamId;
    personal.tmbId = member._id;
    personal.name = name;
    personal.intro = '仅包含当前用户的 RAGFlow 个人知识库；文档仍在 RAGFlow 中维护并自动同步。';
    personal.createTime = new Date();
    personal.updateTime = new Date();
    personal.autoSync = true;
    personal.apiDatasetServer = { apiServer: {
      baseUrl: `http://personal-work-site:8765/api/fastgpt/apidataset/personal/${encodeURIComponent(user.username)}`,
      authorization: personalApiDatasetToken(user.username), basePath: ''
    }};
    const inserted = await datasets.insertOne(personal);
    personal._id = inserted.insertedId;
  } else if (String(personal.teamId) !== String(member.teamId)) {
    // Repair records made by an older version that cloned BSON ObjectIds.
    await datasets.updateOne({ _id: personal._id }, { $set: { teamId: member.teamId, updateTime: new Date() } });
    personal.teamId = member.teamId;
  }
  await ensureDatasetPermission(personal._id, member);

  // Ask FastGPT to import any newly added RAGFlow files. API 文件库 deduplicates
  // by apiFileId, so this is safe on every SSO login and performs no reindex for
  // already imported files.
  try {
    const files = await fastgptRequest(token, '/api/core/dataset/apiDataset/list', { datasetId: String(personal._id), parentId: '' });
    if (Array.isArray(files) && files.length) {
      await fastgptRequest(token, '/api/core/dataset/collection/create/apiCollectionV2', {
        datasetId: String(personal._id), parentId: null, apiFiles: files,
        trainingType: 'chunk', chunkSettings: { trainingType: 'chunk' }
      });
    }
  } catch (error) {
    // Do not reject login if FastGPT is momentarily warming up. The next login
    // (or the UI's normal sync action) retries the idempotent import.
    console.error('[office-personal-kb-sync]', error.message || error);
  }
}

function officeMcpUrl(username) {
  try {
    const config = JSON.parse(fs.readFileSync(process.env.OFFICE_CONFIG_PATH || '/office/config.json', 'utf8'));
    if (!config.mcp_secret) return '';
    return `http://personal-work-site:8765/mcp?access_token=${encodeURIComponent(config.mcp_secret)}&username=${encodeURIComponent(username)}`;
  } catch { return ''; }
}

async function ensureOfficeMcpCollection(user, member) {
  const url = officeMcpUrl(user.username);
  if (!url) return;
  const name = '办公助手 MCP 工具';
  const db = mongo.db('fastgpt');
  const apps = db.collection('apps');
  const permissions = db.collection('resource_permissions');
  const ensurePermission = async (resourceId) => permissions.updateOne(
    { resourceId, resourceType: 'app', tmbId: member._id },
    { $set: { teamId: member.teamId, tmbId: member._id, resourceId, resourceType: 'app', permission: 4294967295 } },
    { upsert: true }
  );
  const existing = await apps.findOne({ tmbId: member._id, name, type: 'toolSet', deleteTime: null });
  if (existing) {
    // BSON ObjectIds are not preserved by structuredClone in every Node build;
    // normalize old copies as well so FastGPT's team filter can see them.
    await apps.updateOne({ _id: existing._id }, { $set: { teamId: member.teamId, updateTime: new Date() } });
    await ensurePermission(existing._id);
    return;
  }
  // Members normally lack the FastGPT "create app" entitlement. Copying the
  // already parsed template gives every account its own private collection and
  // its own MCP identity boundary, without elevating members to team owners.
  const template = await apps.findOne({ name, type: 'toolSet', deleteTime: null });
  if (!template) throw new Error('办公助手 MCP 模板集合尚未创建');
  const copy = structuredClone(template);
  delete copy._id;
  copy.teamId = member.teamId;
  copy.tmbId = member._id;
  copy.createTime = new Date();
  copy.updateTime = new Date();
  if (copy.modules && copy.modules[0] && copy.modules[0].toolConfig && copy.modules[0].toolConfig.mcpToolSet) {
    copy.modules[0].nodeId = crypto.randomBytes(12).toString('base64url');
    copy.modules[0].toolConfig.mcpToolSet.url = url;
  }
  const inserted = await apps.insertOne(copy);
  await ensurePermission(inserted.insertedId);
}

function reply(res, status, body) {
  const raw = Buffer.from(JSON.stringify(body));
  res.writeHead(status, { 'content-type': 'application/json', 'content-length': raw.length });
  res.end(raw);
}

async function login(user) {
  // Every office user, including administrators, receives a separate FastGPT
  // identity. Mapping admins to the shared root session would merge their
  // personal knowledge bases. System-level model provisioning still uses the
  // short-lived /system-token path below and is never sent to browsers.
  const db = mongo.db('fastgpt');
  const username = `office-${String(user.username || '').replace(/[^a-zA-Z0-9_.-]/g, '_')}`;
  if (!user.username) throw new Error('缺少办公助手用户名');
  let account = await db.collection('users').findOne({ username });
  const now = new Date();
  if (!account) {
    const password = crypto.createHash('sha256').update(crypto.randomBytes(32)).digest('hex');
    const created = await db.collection('users').insertOne({
      username, password, status: 'active', timezone: 'Asia/Shanghai', language: 'zh-CN', tags: [],
      createTime: now, promotionRate: 0, meta: { officeUsername: user.username }
    });
    account = { _id: created.insertedId };
  } else {
    await db.collection('users').updateOne({ _id: account._id }, { $set: { status: 'active', meta: { officeUsername: user.username } } });
  }
  const team = await db.collection('teams').findOne({ ownerId: { $exists: true } });
  if (!team) throw new Error('FastGPT 默认团队未初始化');
  let member = await db.collection('team_members').findOne({ teamId: team._id, userId: account._id });
  // In FastGPT, every team owner bypasses private resource permissions. Office
  // administrators must therefore remain ordinary team members here; their
  // administrative rights stay in the office app, while the dedicated root
  // session below handles system-level FastGPT provisioning.
  const role = 'member';
  if (!member) {
    const created = await db.collection('team_members').insertOne({
      teamId: team._id, userId: account._id, name: user.name || user.username, status: 'active', role,
      avatar: user.avatar_url || '/imgs/avatar/AdoraAvatar.svg', createTime: now
    });
    member = { _id: created.insertedId };
  } else {
    await db.collection('team_members').updateOne({ _id: member._id }, { $set: { name: user.name || user.username, role, status: 'active', updateTime: now } });
  }
  await db.collection('users').updateOne({ _id: account._id }, { $set: { lastLoginTmbId: member._id } });
  const token = `${account._id}:${crypto.randomBytes(24).toString('base64url')}`;
  // FastGPT Redis 客户端会给所有键加上 fastgpt: 前缀；缺少此前缀时
  // session 虽写入成功，却永远无法被 tokenLogin 读取。
  const sessionKey = `fastgpt:session:${token}`;
  await redis.hset(sessionKey, { userId: String(account._id), teamId: String(team._id), tmbId: String(member._id), isRoot: '0', createdAt: String(Date.now()), ip: 'office-sso' });
  await redis.expire(sessionKey, 7 * 24 * 60 * 60);
  try { await ensureOfficeMcpCollection(user, member); }
  catch (error) { console.error('[office-mcp-sync]', error.message || error); }
  try { await ensureRagflowDatasets(user, member, token); }
  catch (error) { console.error('[office-ragflow-kb-sync]', error.message || error); }
  return token;
}

// Only the office backend can call this private Docker-network endpoint.  It
// supplies a short-lived FastGPT root session for configuration provisioning
// (model registration), never to a browser or an office end user.
async function systemToken() {
  const db = mongo.db('fastgpt');
  const account = await db.collection('users').findOne({ username: 'root' });
  const team = await db.collection('teams').findOne({ ownerId: { $exists: true } });
  const member = team && account && await db.collection('team_members').findOne({ teamId: team._id, userId: account._id });
  if (!account || !team || !member) throw new Error('FastGPT root account is not initialized');
  const token = `${account._id}:${crypto.randomBytes(24).toString('base64url')}`;
  const sessionKey = `fastgpt:session:${token}`;
  await redis.hset(sessionKey, { userId: String(account._id), teamId: String(team._id), tmbId: String(member._id), isRoot: '1', createdAt: String(Date.now()), ip: 'office-fastgpt-sync' });
  await redis.expire(sessionKey, 60);
  return token;
}

http.createServer(async (req, res) => {
  if (req.method !== 'POST' || !['/login', '/system-token'].includes(req.url) || req.headers['x-office-sso-secret'] !== secret) return reply(res, 403, { error: 'forbidden' });
  let raw = ''; req.on('data', (part) => raw += part); req.on('end', async () => {
    try { reply(res, 200, { token: req.url === '/system-token' ? await systemToken() : await login(JSON.parse(raw || '{}')) }); }
    catch (error) { reply(res, 500, { error: error.message || String(error) }); }
  });
}).listen(3100, '0.0.0.0');

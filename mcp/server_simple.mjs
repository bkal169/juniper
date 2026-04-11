import { createClient } from '@supabase/supabase-js';
import OpenAI from 'openai';
import { createInterface } from 'readline';

const sb = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

async function embed(text) {
  const res = await openai.embeddings.create({
    model: 'text-embedding-3-small',
    input: text.slice(0, 8000)
  });
  return res.data[0].embedding;
}

const TOOLS = {
  capture: async ({ content, source = 'jrih', entry_type = 'observation', tags = [] }) => {
    const embedding = await embed(content);
    const { data, error } = await sb.from('thoughts')
      .insert({ content, source, entry_type, tags, embedding, agent: 'mcp-capture', confidence: 1.0 })
      .select('id, created_at').single();
    if (error) throw error;
    return { captured: true, id: data.id, created_at: data.created_at };
  },

  search: async ({ query, source, limit = 8 }) => {
    const embedding = await embed(query);
    const { data, error } = await sb.rpc('hybrid_search', {
      query_text: query,
      query_embed: embedding,
      source_filter: source || null,
      match_count: limit
    });
    if (error) throw error;
    return { results: data, count: data.length };
  },

  list_recent: async ({ source, limit = 10 }) => {
    let q = sb.from('thoughts')
      .select('id, content, summary, source, entry_type, tags, created_at')
      .order('created_at', { ascending: false })
      .limit(limit);
    if (source) q = q.eq('source', source);
    const { data, error } = await q;
    if (error) throw error;
    return { entries: data, count: data.length };
  },

  stats: async () => {
    const { data } = await sb.from('thoughts').select('source, entry_type');
    const bySource = {}, byType = {};
    data?.forEach(r => {
      bySource[r.source] = (bySource[r.source] || 0) + 1;
      byType[r.entry_type] = (byType[r.entry_type] || 0) + 1;
    });
    return { total: data?.length || 0, by_namespace: bySource, by_type: byType };
  },

  weekly_digest: async () => {
    const since = new Date(Date.now() - 7 * 86400000).toISOString();
    const { data } = await sb.from('thoughts')
      .select('content, source, entry_type, created_at')
      .gte('created_at', since)
      .order('created_at', { ascending: true });
    return { raw_entries: data?.slice(0, 50), entry_count: data?.length, period: { from: since, to: new Date().toISOString() } };
  }
};

// MCP stdio protocol
const rl = createInterface({ input: process.stdin });

process.stdout.write(JSON.stringify({
  jsonrpc: '2.0', method: 'notifications/initialized', params: {}
}) + '\n');

rl.on('line', async (line) => {
  try {
    const msg = JSON.parse(line);

    if (msg.method === 'initialize') {
      process.stdout.write(JSON.stringify({
        jsonrpc: '2.0', id: msg.id,
        result: {
          protocolVersion: '2024-11-05',
          capabilities: { tools: {} },
          serverInfo: { name: 'jrih-brain', version: '1.0.0' }
        }
      }) + '\n');
      return;
    }

    if (msg.method === 'tools/list') {
      process.stdout.write(JSON.stringify({
        jsonrpc: '2.0', id: msg.id,
        result: {
          tools: [
            { name: 'capture', description: 'Write a thought to the JRIH brain', inputSchema: { type: 'object', properties: { content: { type: 'string' }, source: { type: 'string' }, entry_type: { type: 'string' }, tags: { type: 'array' } }, required: ['content'] } },
            { name: 'search', description: 'Hybrid semantic + keyword search of the brain', inputSchema: { type: 'object', properties: { query: { type: 'string' }, source: { type: 'string' }, limit: { type: 'number' } }, required: ['query'] } },
            { name: 'list_recent', description: 'List recent brain entries', inputSchema: { type: 'object', properties: { source: { type: 'string' }, limit: { type: 'number' } } } },
            { name: 'stats', description: 'Brain health stats', inputSchema: { type: 'object', properties: {} } },
            { name: 'weekly_digest', description: 'Get this weeks entries for synthesis', inputSchema: { type: 'object', properties: {} } }
          ]
        }
      }) + '\n');
      return;
    }

    if (msg.method === 'tools/call') {
      const { name, arguments: args } = msg.params;
      if (!TOOLS[name]) throw new Error(`Unknown tool: ${name}`);
      const result = await TOOLS[name](args || {});
      process.stdout.write(JSON.stringify({
        jsonrpc: '2.0', id: msg.id,
        result: { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] }
      }) + '\n');
      return;
    }

  } catch (err) {
    process.stdout.write(JSON.stringify({
      jsonrpc: '2.0', id: null,
      error: { code: -32603, message: err.message }
    }) + '\n');
  }
});

process.stderr.write('JRIH Brain MCP server started (5 tools)\n');
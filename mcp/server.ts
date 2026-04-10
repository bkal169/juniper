/**
 * JRIH Second Brain — MCP Server
 * 5 tools for Claude Desktop integration.
 *
 * Tools:
 *   capture  — Write a thought to the brain
 *   search   — Hybrid search (BM25 + vector)
 *   list_recent — List recent thoughts by namespace
 *   weekly_digest — Get latest weekly digest
 *   stats    — Brain health metrics
 */

import { createClient } from '@supabase/supabase-js';
import OpenAI from 'openai';

const supabase = createClient(
  process.env.SUPABASE_URL || 'https://ubdhpacoqmlxudcvhyuu.supabase.co',
  process.env.SUPABASE_SERVICE_KEY || ''
);

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

async function embed(text: string): Promise<number[]> {
  const response = await openai.embeddings.create({
    model: 'text-embedding-3-small',
    input: text.slice(0, 8000),
  });
  return response.data[0].embedding;
}

// ═══════════════════════════════════════════════════════════
// TOOL: capture
// ═══════════════════════════════════════════════════════════

interface CaptureArgs {
  content: string;
  source?: string;
  entry_type?: string;
  tags?: string[];
  ttl_days?: number;
}

async function capture(args: CaptureArgs) {
  const embedding = await embed(args.content);

  const row: Record<string, unknown> = {
    content: args.content,
    source: args.source || 'jrih',
    entry_type: args.entry_type || 'observation',
    agent: 'mcp-capture',
    tags: args.tags || [],
    embedding,
    confidence: 1.0,
  };

  if (args.ttl_days) {
    row.ttl = `${args.ttl_days} days`;
  }

  const { data, error } = await supabase
    .from('thoughts')
    .insert(row)
    .select('id')
    .single();

  if (error) throw new Error(`Capture failed: ${error.message}`);
  return { id: data.id, status: 'captured', source: row.source };
}

// ═══════════════════════════════════════════════════════════
// TOOL: search
// ═══════════════════════════════════════════════════════════

interface SearchArgs {
  query: string;
  source?: string;
  entry_type?: string;
  limit?: number;
}

async function search(args: SearchArgs) {
  const queryEmbedding = await embed(args.query);

  const { data, error } = await supabase.rpc('hybrid_search', {
    query_text: args.query,
    query_embedding: queryEmbedding,
    match_count: args.limit || 10,
    source_filter: args.source || null,
    entry_type_filter: args.entry_type || null,
  });

  if (error) throw new Error(`Search failed: ${error.message}`);

  return (data || []).map((r: Record<string, unknown>) => ({
    id: r.id,
    content: r.content,
    source: r.source,
    entry_type: r.entry_type,
    tags: r.tags,
    confidence: r.confidence,
    created_at: r.created_at,
    score: r.rrf_score,
  }));
}

// ═══════════════════════════════════════════════════════════
// TOOL: list_recent
// ═══════════════════════════════════════════════════════════

interface ListRecentArgs {
  source?: string;
  limit?: number;
  entry_type?: string;
}

async function listRecent(args: ListRecentArgs) {
  let query = supabase
    .from('thoughts')
    .select('id, content, source, entry_type, tags, confidence, created_at')
    .order('created_at', { ascending: false })
    .limit(args.limit || 20);

  if (args.source) query = query.eq('source', args.source);
  if (args.entry_type) query = query.eq('entry_type', args.entry_type);

  const { data, error } = await query;
  if (error) throw new Error(`List failed: ${error.message}`);

  return (data || []).map((r) => ({
    ...r,
    content: (r.content as string).slice(0, 300),
  }));
}

// ═══════════════════════════════════════════════════════════
// TOOL: weekly_digest
// ═══════════════════════════════════════════════════════════

async function weeklyDigest() {
  const { data, error } = await supabase
    .from('digests')
    .select('*')
    .order('created_at', { ascending: false })
    .limit(1)
    .single();

  if (error) return { status: 'no_digest', message: 'No weekly digest found.' };
  return data;
}

// ═══════════════════════════════════════════════════════════
// TOOL: stats
// ═══════════════════════════════════════════════════════════

async function stats() {
  const { data, error } = await supabase.rpc('juniper_stats', { days: 7 });

  if (error) throw new Error(`Stats failed: ${error.message}`);
  return data?.[0] || {};
}

// ═══════════════════════════════════════════════════════════
// MCP SERVER (stdio transport)
// ═══════════════════════════════════════════════════════════

const TOOLS = {
  capture: {
    description: 'Write a thought to the JRIH Second Brain',
    parameters: {
      type: 'object',
      properties: {
        content: { type: 'string', description: 'The thought content' },
        source: { type: 'string', description: 'Namespace: jrih, axiom, lumena, aro, personal, content, infra, intel, heart_of_juniper' },
        entry_type: { type: 'string', description: 'Type: observation, decision, task, reference, insight, question, flagged' },
        tags: { type: 'array', items: { type: 'string' }, description: 'Tags for categorization' },
        ttl_days: { type: 'number', description: 'Days until expiry (null = permanent)' },
      },
      required: ['content'],
    },
    handler: capture,
  },
  search: {
    description: 'Search the JRIH Second Brain using hybrid BM25 + vector search',
    parameters: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Search query' },
        source: { type: 'string', description: 'Filter by namespace' },
        entry_type: { type: 'string', description: 'Filter by entry type' },
        limit: { type: 'number', description: 'Max results (default 10)' },
      },
      required: ['query'],
    },
    handler: search,
  },
  list_recent: {
    description: 'List recent thoughts from the brain, optionally filtered by namespace',
    parameters: {
      type: 'object',
      properties: {
        source: { type: 'string', description: 'Filter by namespace' },
        limit: { type: 'number', description: 'Max results (default 20)' },
        entry_type: { type: 'string', description: 'Filter by entry type' },
      },
    },
    handler: listRecent,
  },
  weekly_digest: {
    description: 'Get the latest weekly digest from the JRIH brain',
    parameters: { type: 'object', properties: {} },
    handler: weeklyDigest,
  },
  stats: {
    description: 'Get JRIH brain health metrics and Juniper operational stats',
    parameters: { type: 'object', properties: {} },
    handler: stats,
  },
};

// Stdin/stdout MCP protocol handler
process.stdin.setEncoding('utf-8');

let buffer = '';
process.stdin.on('data', (chunk: string) => {
  buffer += chunk;
  const lines = buffer.split('\n');
  buffer = lines.pop() || '';

  for (const line of lines) {
    if (!line.trim()) continue;
    handleMessage(JSON.parse(line));
  }
});

async function handleMessage(msg: { id?: string | number; method?: string; params?: Record<string, unknown> }) {
  const { id, method, params } = msg;

  if (method === 'initialize') {
    respond(id, {
      protocolVersion: '2024-11-05',
      capabilities: { tools: {} },
      serverInfo: { name: 'jrih-brain', version: '1.0.0' },
    });
  } else if (method === 'tools/list') {
    respond(id, {
      tools: Object.entries(TOOLS).map(([name, tool]) => ({
        name,
        description: tool.description,
        inputSchema: tool.parameters,
      })),
    });
  } else if (method === 'tools/call') {
    const toolName = params?.name as string;
    const toolArgs = (params?.arguments || {}) as Record<string, unknown>;
    const tool = TOOLS[toolName as keyof typeof TOOLS];

    if (!tool) {
      respondError(id, `Unknown tool: ${toolName}`);
      return;
    }

    try {
      const result = await tool.handler(toolArgs as never);
      respond(id, {
        content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
      });
    } catch (e) {
      respondError(id, (e as Error).message);
    }
  }
}

function respond(id: string | number | undefined, result: unknown) {
  process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, result }) + '\n');
}

function respondError(id: string | number | undefined, message: string) {
  process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, error: { code: -32000, message } }) + '\n');
}

console.error('JRIH Brain MCP server started (5 tools)');

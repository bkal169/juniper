/**
 * JRIH Second Brain — MCP Server
 * 6 tools for Claude Desktop integration.
 *
 * Tools:
 *   capture       — Write a thought to the brain
 *   search        — Hybrid search (BM25 + vector), raw results
 *   retrieve      — Upgraded RAG: expand → multi-search → grade → rewrite → synthesize
 *   list_recent   — List recent thoughts by namespace
 *   weekly_digest — Get latest weekly digest
 *   stats         — Brain health metrics
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
// TOOL: retrieve
// Upgraded RAG: expand → multi-search → grade → rewrite → synthesize
// retrieve > load: tight queries, confidence-weighted synthesis, citations
// ═══════════════════════════════════════════════════════════

interface RetrieveArgs {
  query: string;
  source?: string;
  entry_type?: string;
}

interface ThoughtRow {
  id: string;
  content: string;
  summary: string | null;
  source: string;
  entry_type: string;
  tags: string[];
  confidence: number;
  created_at: string;
  rrf_score: number;
}

async function expandQuery(query: string): Promise<string[]> {
  const resp = await openai.chat.completions.create({
    model: 'gpt-4o-mini',
    messages: [
      {
        role: 'user',
        content:
          'Generate 2 alternative search queries for this question. ' +
          'Different angles, same intent. Return a JSON array of strings only.\n\n' +
          `Query: ${query}\n\nJSON:`,
      },
    ],
    max_tokens: 200,
    temperature: 0.3,
  });
  const text = resp.choices[0]?.message?.content || '[]';
  try {
    const start = text.indexOf('[');
    const end = text.lastIndexOf(']') + 1;
    return start >= 0 ? JSON.parse(text.slice(start, end)) : [];
  } catch {
    return [];
  }
}

async function multiSearch(
  queries: string[],
  source: string | null,
  entryType: string | null,
  limit: number,
): Promise<ThoughtRow[]> {
  const seen = new Map<string, ThoughtRow>();
  for (const q of queries.slice(0, 3)) {
    const emb = await embed(q);
    const { data } = await supabase.rpc('hybrid_search', {
      query_text: q,
      query_embedding: emb,
      match_count: limit,
      source_filter: source,
      entry_type_filter: entryType,
    });
    for (const row of (data || []) as ThoughtRow[]) {
      const existing = seen.get(row.id);
      if (!existing || row.rrf_score > existing.rrf_score) {
        seen.set(row.id, row);
      }
    }
  }
  return [...seen.values()].sort((a, b) => b.rrf_score - a.rrf_score).slice(0, 10);
}

function gradeResults(results: ThoughtRow[]): 'good' | 'poor' | 'empty' {
  if (!results.length) return 'empty';
  const topScore = results[0].rrf_score;
  const highConf = results.filter(r => (r.confidence ?? 0) >= 0.7).length;
  const uniqueSources = new Set(results.slice(0, 5).map(r => r.source)).size;
  if (topScore >= 0.015 && highConf >= 2 && uniqueSources >= 2) return 'good';
  if (topScore >= 0.010 && results.length >= 2) return 'poor';
  return 'empty';
}

async function rewriteQuery(query: string): Promise<string> {
  const resp = await openai.chat.completions.create({
    model: 'gpt-4o-mini',
    messages: [
      {
        role: 'user',
        content:
          'This search query returned poor results from a knowledge base. ' +
          'Rewrite it more broadly or from a different angle. ' +
          'Return only the rewritten query, no explanation.\n\n' +
          `Original: ${query}`,
      },
    ],
    max_tokens: 100,
    temperature: 0.4,
  });
  return resp.choices[0]?.message?.content?.trim() || query;
}

async function synthesizeAnswer(query: string, results: ThoughtRow[]): Promise<{ answer: string; citations: string[] }> {
  const top = results.slice(0, 7);
  const citations: string[] = [];
  const contextParts: string[] = [];

  for (let i = 0; i < top.length; i++) {
    const r = top[i];
    const text = r.summary || r.content.slice(0, 400);
    const src = `${r.source}/${r.entry_type}`;
    citations.push(`[${i + 1}] ${src} (conf:${(r.confidence ?? 0).toFixed(2)}, score:${r.rrf_score.toFixed(4)})`);
    contextParts.push(`[${i + 1}] ${src} conf:${(r.confidence ?? 0).toFixed(2)}\n${text}`);
  }

  const resp = await openai.chat.completions.create({
    model: 'gpt-4o',
    messages: [
      {
        role: 'user',
        content:
          'Answer this query using only the provided knowledge base entries. ' +
          'Cite sources inline by number [1], [2] etc. Be concise and direct.\n\n' +
          `Query: ${query}\n\nKnowledge base:\n${contextParts.join('\n\n')}\n\nAnswer:`,
      },
    ],
    max_tokens: 800,
  });

  return {
    answer: resp.choices[0]?.message?.content || 'No answer generated.',
    citations,
  };
}

async function retrieve(args: RetrieveArgs) {
  const source = args.source || null;
  const entryType = args.entry_type || null;

  // Expand → multi-search
  const alternatives = await expandQuery(args.query);
  const allQueries = [args.query, ...alternatives];
  let results = await multiSearch(allQueries, source, entryType, 8);
  let grade = gradeResults(results);

  // Rewrite + retry once if poor
  if (grade !== 'good') {
    const rewritten = await rewriteQuery(args.query);
    const retryQueries = [rewritten, ...alternatives];
    const retryResults = await multiSearch(retryQueries, null, null, 8);
    const retryGrade = gradeResults(retryResults);
    if (retryGrade !== 'empty') {
      results = retryResults;
      grade = retryGrade;
    }
  }

  if (!results.length) {
    return {
      answer: `No relevant entries found for: ${args.query}. Consider capturing this topic via brain.capture().`,
      citations: [],
      grade: 'empty',
      result_count: 0,
    };
  }

  const { answer, citations } = await synthesizeAnswer(args.query, results);
  return { answer, citations, grade, result_count: results.length };
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
  retrieve: {
    description: 'Upgraded RAG: expand query → multi-search → grade → rewrite-retry → synthesize with citations. Use this for questions that need a synthesized answer, not raw results.',
    parameters: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Natural-language question or topic' },
        source: { type: 'string', description: 'Optional namespace filter (jrih, axiom, intel, infra, …)' },
        entry_type: { type: 'string', description: 'Optional type filter (decision, insight, reference, …)' },
      },
      required: ['query'],
    },
    handler: retrieve,
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
      serverInfo: { name: 'jrih-brain', version: '1.1.0' },
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

console.error('JRIH Brain MCP server started (6 tools: +retrieve)');

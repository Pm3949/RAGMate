// supabaseClient.ts — Supabase has been replaced by our custom Python backend.
// This stub prevents build errors in files that still reference `supabase`.
// All active code uses fetch() against VITE_API_BASE_URL instead.

const noop = () => Promise.resolve({ data: null, error: null });

export const supabase = {
  auth: {
    getSession: noop,
    getUser: noop,
    signOut: noop,
    onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } }),
  },
  from: (_table: string) => ({
    select: () => ({ data: [], error: null }),
    insert: () => ({ data: null, error: null }),
    update: () => ({ data: null, error: null }),
    delete: () => ({ data: null, error: null }),
    eq: function() { return this; },
    order: function() { return this; },
    limit: function() { return this; },
  }),
  channel: (_name: string) => ({
    on: function() { return this; },
    subscribe: function() { return this; },
  }),
  removeChannel: noop,
};
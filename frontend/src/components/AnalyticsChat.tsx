import React, { useState } from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Bot, Send } from 'lucide-react';
import { api } from '../services/api';
import type { AnalyticsChatResponse } from '../types';

const examples = [
  '¿Qué platillos tuvieron más comentarios negativos en los últimos 7 días?',
  'Muéstrame los mejores platillos del último mes',
  '¿Cuáles son los aspectos del establecimiento más mencionados?',
];

export const AnalyticsChat: React.FC = () => {
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState<AnalyticsChatResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (question.trim().length < 3 || loading) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await api.askAnalytics(question.trim()));
    } catch (err: any) {
      setError(err.message || 'No se pudo consultar la estadística.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="bg-white border border-slate-200 rounded-2xl shadow-2xs p-6 space-y-4">
      <div className="flex items-center gap-2.5">
        <div className="p-2 bg-indigo-50 text-indigo-600 rounded-xl"><Bot className="w-5 h-5" /></div>
        <div><h2 className="text-base font-bold text-slate-900">Chat de estadísticas</h2><p className="text-xs text-slate-500">Consulta las reseñas con Llama 3.2 y recibe datos listos para graficar.</p></div>
      </div>
      <form onSubmit={submit} className="flex gap-2">
        <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ej. ¿Qué platillos tienen más quejas este mes?" className="min-w-0 flex-1 rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-indigo-500" />
        <button type="submit" disabled={loading || question.trim().length < 3} className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white disabled:opacity-50 cursor-pointer"><Send className="w-3.5 h-3.5" />{loading ? 'Consultando...' : 'Preguntar'}</button>
      </form>
      <div className="flex flex-wrap gap-2">{examples.map((example) => <button key={example} type="button" onClick={() => setQuestion(example)} className="rounded-lg bg-slate-100 px-2.5 py-1.5 text-[11px] text-slate-600 hover:bg-indigo-50 cursor-pointer">{example}</button>)}</div>
      {error && <p className="rounded-xl bg-rose-50 p-3 text-xs text-rose-700">{error}</p>}
      {result && <div className="space-y-3 rounded-xl border border-slate-100 bg-slate-50 p-4"><p className="text-sm text-slate-700">{result.respuesta}</p><p className="text-[11px] text-slate-500">{result.consulta_interpretada.metrica} · {result.consulta_interpretada.agrupacion} · últimos {result.consulta_interpretada.periodo_dias} días</p>{result.grafica.datos.length > 0 && <div className="h-64 bg-white rounded-xl p-2"><p className="px-2 pt-1 text-xs font-bold text-slate-700">{result.grafica.titulo}</p><ResponsiveContainer width="100%" height="90%"><BarChart data={result.grafica.datos} margin={{ top: 12, right: 16, left: 0, bottom: 5 }}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="etiqueta" tick={{ fontSize: 10 }} /><YAxis allowDecimals={false} tick={{ fontSize: 10 }} /><Tooltip /><Bar dataKey="valor" fill="#6366f1" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div>}</div>}
    </section>
  );
};

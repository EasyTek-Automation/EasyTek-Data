'use client';

import { useEffect, useState } from 'react';
import { Header } from '@/components/Header';
import { BottomNav } from '@/components/BottomNav';
import { OEECard } from '@/components/OEECard';
import { LoadingSpinner } from '@/components/LoadingSpinner';

interface UserProfile {
  username: string;
  email: string;
  level: number;
  perfil: string;
}

interface OEEData {
  resumo: {
    oee: number;
    disponibilidade: number;
    performance: number;
    qualidade: number;
  };
  total_registros: number;
}

export default function DashboardMobile() {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [oeeData, setOeeData] = useState<OEEData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Buscar perfil do usuário
        const userRes = await fetch('/api/v1/user/profile', {
          credentials: 'include',
        });

        if (!userRes.ok) {
          throw new Error('Não autenticado');
        }

        const userData = await userRes.json();
        setUser(userData);

        // Buscar dados de OEE
        const oeeRes = await fetch('/api/v1/producao/oee?linha=LCT08', {
          credentials: 'include',
        });

        if (oeeRes.ok) {
          const oeeJson = await oeeRes.json();
          if (oeeJson.status === 'success') {
            setOeeData(oeeJson.data);
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Erro ao carregar dados');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return <LoadingSpinner />;
  }

  if (error || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-primary">
        <div className="bg-white rounded-2xl p-8 max-w-sm mx-4 text-center shadow-2xl">
          <div className="text-6xl mb-4">🔒</div>
          <h1 className="text-2xl font-bold text-gray-800 mb-2">
            Acesso Restrito
          </h1>
          <p className="text-gray-600 mb-6">
            Faça login para acessar o dashboard mobile.
          </p>
          <a
            href="/login"
            className="inline-block bg-primary-500 text-white px-6 py-3 rounded-lg font-semibold hover:bg-primary-600 transition"
          >
            Fazer Login
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-teal-50 via-blue-50 to-purple-50 pb-20">
      <Header user={user} />

      <main className="p-4 space-y-6 animate-slide-up">
        {/* Saudação */}
        <div className="bg-white rounded-2xl p-6 shadow-lg">
          <h1 className="text-2xl font-bold text-gray-800">
            Olá, {user.username.split(' ')[0]}! 👋
          </h1>
          <p className="text-gray-600 mt-1">
            Bem-vindo ao dashboard mobile
          </p>
        </div>

        {/* Cards de OEE */}
        <div className="grid grid-cols-2 gap-4">
          <OEECard
            title="OEE Geral"
            value={oeeData?.resumo?.oee || 0}
            trend={+2.3}
            color="green"
            icon="📊"
          />
          <OEECard
            title="Disponibilidade"
            value={oeeData?.resumo?.disponibilidade || 0}
            trend={-1.1}
            color="blue"
            icon="⚡"
          />
          <OEECard
            title="Performance"
            value={oeeData?.resumo?.performance || 0}
            trend={+0.8}
            color="purple"
            icon="🚀"
          />
          <OEECard
            title="Qualidade"
            value={oeeData?.resumo?.qualidade || 0}
            trend={+0.3}
            color="orange"
            icon="✨"
          />
        </div>

        {/* Informações Adicionais */}
        <div className="bg-white rounded-2xl p-6 shadow-lg">
          <h2 className="text-lg font-bold text-gray-800 mb-4">
            Informações do Usuário
          </h2>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Perfil:</span>
              <span className="font-semibold text-gray-800 capitalize">
                {user.perfil}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Nível de Acesso:</span>
              <span className="font-semibold text-gray-800">
                {user.level === 3 ? 'Administrador' : user.level === 2 ? 'Avançado' : 'Básico'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Email:</span>
              <span className="font-semibold text-gray-800 text-xs">
                {user.email}
              </span>
            </div>
          </div>
        </div>
      </main>

      <BottomNav />
    </div>
  );
}

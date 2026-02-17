'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';

export function BottomNav() {
  const pathname = usePathname();

  const navItems = [
    { href: '/mobile', icon: '🏠', label: 'Home' },
    { href: '/mobile/producao', icon: '📊', label: 'Produção' },
    { href: '/mobile/manutencao', icon: '⚙️', label: 'Manutenção' },
    { href: '/mobile/perfil', icon: '👤', label: 'Perfil' },
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 shadow-lg z-50">
      <div className="flex justify-around items-center h-16">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex flex-col items-center justify-center flex-1 h-full transition-colors ${
                isActive
                  ? 'text-primary-500'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <span className="text-2xl mb-1">{item.icon}</span>
              <span className={`text-xs font-medium ${isActive ? 'font-bold' : ''}`}>
                {item.label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

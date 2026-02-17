interface HeaderProps {
  user: {
    username: string;
    level: number;
    perfil: string;
  };
}

export function Header({ user }: HeaderProps) {
  return (
    <header className="bg-gradient-primary text-white p-4 shadow-lg sticky top-0 z-50">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="bg-white/20 backdrop-blur-sm rounded-full p-2">
            <svg
              className="w-8 h-8"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
              />
            </svg>
          </div>
          <div>
            <h1 className="text-lg font-bold">AMG Data</h1>
            <p className="text-xs text-white/80">Mobile Dashboard</p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {/* Badge de nível */}
          <div className="bg-white/20 backdrop-blur-sm px-3 py-1 rounded-full text-xs font-semibold">
            Nível {user.level}
          </div>

          {/* Avatar */}
          <div className="w-10 h-10 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center font-bold text-sm">
            {user.username.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)}
          </div>
        </div>
      </div>
    </header>
  );
}

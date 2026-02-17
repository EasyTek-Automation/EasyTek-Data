interface OEECardProps {
  title: string;
  value: number;
  trend: number;
  color: 'green' | 'blue' | 'purple' | 'orange';
  icon: string;
}

const colorClasses = {
  green: 'from-green-400 to-emerald-600',
  blue: 'from-blue-400 to-cyan-600',
  purple: 'from-purple-400 to-violet-600',
  orange: 'from-orange-400 to-amber-600',
};

export function OEECard({ title, value, trend, color, icon }: OEECardProps) {
  const isPositive = trend > 0;

  return (
    <div className="bg-white rounded-2xl p-5 shadow-lg hover:shadow-xl transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="text-3xl">{icon}</div>
        <div
          className={`text-xs font-semibold px-2 py-1 rounded-full flex items-center space-x-1 ${
            isPositive
              ? 'bg-green-100 text-green-700'
              : 'bg-red-100 text-red-700'
          }`}
        >
          <span>{isPositive ? '↗' : '↘'}</span>
          <span>{Math.abs(trend)}%</span>
        </div>
      </div>

      <h3 className="text-sm font-medium text-gray-600 mb-2">{title}</h3>

      <div className="flex items-end space-x-2">
        <span className="text-3xl font-bold text-gray-900">
          {value.toFixed(1)}
        </span>
        <span className="text-xl font-semibold text-gray-500 mb-1">%</span>
      </div>

      {/* Barra de progresso */}
      <div className="mt-4 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full bg-gradient-to-r ${colorClasses[color]} transition-all duration-500`}
          style={{ width: `${Math.min(value, 100)}%` }}
        />
      </div>
    </div>
  );
}

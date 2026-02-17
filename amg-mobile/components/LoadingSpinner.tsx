export function LoadingSpinner() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-primary">
      <div className="text-center">
        <div className="relative w-20 h-20 mx-auto mb-6">
          <div className="absolute inset-0 border-4 border-white/30 rounded-full"></div>
          <div className="absolute inset-0 border-4 border-white border-t-transparent rounded-full animate-spin"></div>
        </div>
        <p className="text-white text-lg font-semibold">Carregando...</p>
        <p className="text-white/70 text-sm mt-2">AMG Data Mobile</p>
      </div>
    </div>
  );
}

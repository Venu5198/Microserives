import React, { useEffect, useState } from 'react';
import { Activity, CheckCircle2, AlertCircle, RefreshCw, Server } from 'lucide-react';
import { apiClient } from '../../api/client';

export const AdminHealth: React.FC = () => {
  const [healthData, setHealthData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchHealth = async () => {
    try {
      const res = await apiClient.get('/health/services');
      setHealthData(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Distributed Microservices Health Monitor</h2>
          <p className="text-xs text-gray-500">Live readiness probes aggregated across all 8 backend nodes</p>
        </div>
        <button
          onClick={fetchHealth}
          className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 rounded-lg text-xs font-semibold text-gray-700 hover:bg-gray-50"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {loading && !healthData ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600"></div>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Overall status banner */}
          <div
            className={`p-4 rounded-xl flex items-center justify-between border ${
              healthData?.system_ready
                ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                : 'bg-amber-50 border-amber-200 text-amber-800'
            }`}
          >
            <div className="flex items-center gap-3">
              {healthData?.system_ready ? (
                <CheckCircle2 className="w-6 h-6 text-emerald-600" />
              ) : (
                <AlertCircle className="w-6 h-6 text-amber-600" />
              )}
              <div>
                <span className="font-bold text-sm block">
                  {healthData?.system_ready ? 'All Microservices Fully Operational' : 'Degraded Connectivity Detected'}
                </span>
                <span className="text-xs opacity-80">Gateway: {healthData?.gateway_status}</span>
              </div>
            </div>
            <span className="text-xs font-mono">Auto-polling: 5s</span>
          </div>

          {/* Grid of Microservices */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {healthData?.services &&
              Object.entries(healthData.services).map(([serviceName, info]: [string, any]) => {
                const isUp = info.status === 'UP';
                return (
                  <div
                    key={serviceName}
                    className="p-4 bg-gray-50 border border-gray-200 rounded-xl flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <Server className="w-4 h-4 text-gray-600" />
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                            isUp ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'
                          }`}
                        >
                          {info.status}
                        </span>
                      </div>
                      <h4 className="font-bold text-gray-900 text-sm truncate">{serviceName}</h4>
                      <p className="text-xs text-gray-500 mt-1">
                        DB: {info.details?.database || 'offline'}
                      </p>
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      )}
    </div>
  );
};


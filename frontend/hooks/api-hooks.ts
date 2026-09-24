"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import type {
  Alert,
  ApiSuccess,
  ChatResponse,
  DashboardData,
  ScenarioResult,
  ShipmentDetail,
  ShipmentListItem,
  SupplierDetail,
  SupplierListItem,
} from "@/types/api";

// --- Dashboard ---
export function useDashboard(filters: Record<string, string | undefined> = {}) {
  return useQuery({
    queryKey: ["dashboard", filters],
    queryFn: () => apiClient.get<ApiSuccess<DashboardData>>("/dashboard", filters),
  });
}

// --- Shipments ---
export interface ShipmentFilters {
  page?: number;
  page_size?: number;
  search?: string;
  region?: string;
  market?: string;
  shipping_mode?: string;
  risk_level?: string;
  status?: string;
  sort_by?: string;
  sort_dir?: string;
}

export function useShipments(filters: ShipmentFilters) {
  return useQuery({
    queryKey: ["shipments", filters],
    queryFn: () =>
      apiClient.get<ApiSuccess<ShipmentListItem[]>>("/shipments", filters as Record<string, string | number>),
    placeholderData: (prev) => prev,
  });
}

export function useShipment(id: number | null) {
  return useQuery({
    queryKey: ["shipment", id],
    queryFn: () => apiClient.get<ApiSuccess<ShipmentDetail>>(`/shipments/${id}`),
    enabled: id !== null,
  });
}

export function useShipmentRecommendations(id: number | null) {
  return useQuery({
    queryKey: ["shipment-recommendations", id],
    queryFn: () => apiClient.get<ApiSuccess<ShipmentDetail["recommendations"]>>(`/shipments/${id}/recommendations`),
    enabled: id !== null,
  });
}

// --- Suppliers ---
export function useSuppliers(filters: Record<string, string | number | undefined> = {}) {
  return useQuery({
    queryKey: ["suppliers", filters],
    queryFn: () => apiClient.get<ApiSuccess<SupplierListItem[]>>("/suppliers", filters),
    placeholderData: (prev) => prev,
  });
}

export function useSupplier(id: number | null) {
  return useQuery({
    queryKey: ["supplier", id],
    queryFn: () => apiClient.get<ApiSuccess<SupplierDetail>>(`/suppliers/${id}`),
    enabled: id !== null,
  });
}

export function useSupplierComparison(ids: number[]) {
  return useQuery({
    queryKey: ["supplier-comparison", ids],
    queryFn: () =>
      apiClient.get<ApiSuccess<{ suppliers: SupplierDetail[] }>>("/suppliers/compare", {
        supplier_ids: ids.join(","),
      }),
    enabled: ids.length > 0,
  });
}

// --- Alerts ---
export function useAlerts(filters: Record<string, string | number | undefined> = {}) {
  return useQuery({
    queryKey: ["alerts", filters],
    queryFn: () => apiClient.get<ApiSuccess<Alert[]>>("/alerts", filters),
  });
}

export function useAcknowledgeAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiClient.post(`/alerts/${id}/acknowledge`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

export function useResolveAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiClient.post(`/alerts/${id}/resolve`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

// --- Analytics ---
export function useAnalytics(endpoint: "delays" | "routes" | "products" | "risk", filters: Record<string, string | undefined> = {}) {
  return useQuery({
    queryKey: ["analytics", endpoint, filters],
    queryFn: () => apiClient.get<ApiSuccess<Record<string, unknown>>>(`/analytics/${endpoint}`, filters),
  });
}

// --- Scenarios ---
export function useRunScenario() {
  return useMutation({
    mutationFn: (payload: {
      shipment_code: string;
      shipping_mode?: string;
      supplier_code?: string;
      scheduled_shipping_days?: number;
      order_item_quantity?: number;
    }) => apiClient.post<ApiSuccess<ScenarioResult>>("/scenarios/run", payload),
  });
}

// --- AI Copilot ---
export function useSendChatMessage() {
  return useMutation({
    mutationFn: (payload: { message: string; conversation_id?: number }) =>
      apiClient.post<ApiSuccess<ChatResponse>>("/ai/chat", payload),
  });
}

// --- Models ---
export function useModels() {
  return useQuery({
    queryKey: ["models"],
    queryFn: () => apiClient.get<ApiSuccess<Record<string, unknown>[]>>("/models"),
  });
}

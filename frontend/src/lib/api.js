import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("rp_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function formatErr(e) {
  const d = e?.response?.data?.detail;
  if (!d) return e?.message || "Something went wrong";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg || JSON.stringify(x)).join(" ");
  return JSON.stringify(d);
}

export const ROLE_LABELS = {
  admin: "Admin",
  master_distributor: "Master Distributor",
  distributor: "Distributor",
  retailer: "Retailer",
};

export const SERVICES = [
  { code: "mobile_prepaid", name: "Mobile Prepaid", icon: "Smartphone" },
  { code: "dth", name: "DTH", icon: "Tv" },
  { code: "electricity", name: "Electricity", icon: "Zap" },
  { code: "data_card", name: "Data Card", icon: "Wifi" },
];

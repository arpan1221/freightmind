import axios from "axios";

import { getApiBaseUrl } from "./getApiBaseUrl";

const api = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 90000,
});

export default api;
export { getApiBaseUrl };

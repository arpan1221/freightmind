import axios from "axios";

import { getApiBaseUrl } from "./getApiBaseUrl";

const api = axios.create({
  baseURL: getApiBaseUrl(),
});

export default api;
export { getApiBaseUrl };

import { server } from "./server.js";
const port = Number(process.env.PORT ?? 8080);
server.listen(port, "0.0.0.0", () => process.stdout.write(`payments listening on ${port}\n`));
process.on("SIGTERM", () => server.close(() => process.exit(0)));

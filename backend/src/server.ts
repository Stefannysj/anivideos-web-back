import { buildApp } from './app.js';
import { readEnvironment } from './config/environment.js';

async function main(): Promise<void> {
  const config = readEnvironment();
  const app = await buildApp(config);
  let closing = false;

  /** Cierra conexiones al detener el proceso para evitar cortes innecesarios. */
  async function shutdown(signal: string): Promise<void> {
    if (closing) return;
    closing = true;
    app.log.info({ signal }, 'Cerrando AniVideos API');
    const deadline = setTimeout(() => process.exit(1), 10_000);
    deadline.unref();
    try {
      await app.close();
    } catch (error) {
      app.log.error({ err: error }, 'No se pudo cerrar la API correctamente');
      process.exitCode = 1;
    } finally {
      clearTimeout(deadline);
    }
  }

  process.once('SIGINT', () => { void shutdown('SIGINT'); });
  process.once('SIGTERM', () => { void shutdown('SIGTERM'); });
  try {
    await app.listen({ port: config.port, host: config.host });
  } catch (error) {
    await app.close();
    throw error;
  }
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : 'No se pudo iniciar AniVideos API.');
  process.exitCode = 1;
});

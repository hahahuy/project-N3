declare module "*esmini.js" {
  type EsminiVector<T> = T[] | { size(): number };

  type EsminiModule = {
    FS: { writeFile(path: string, data: string): void };
    OpenScenario: new (path: string, config: Record<string, number>) => {
      step_frame(dt: number): { simulation_time: number; object_states: EsminiVector<unknown> };
      reset(): void;
      get_road_geometry(): {
        lane_surfaces: EsminiVector<unknown>;
        road_marks: EsminiVector<unknown>;
      };
    };
  };

  const createEsminiModule: (options?: Record<string, unknown>) => Promise<EsminiModule>;
  export default createEsminiModule;
}

from typing import Callable
import dlt
from dlt_source_notion import source, DatabaseResource, DatabaseProperty

DEV_MODE = True


def load_notion_data() -> None:
    pipeline = dlt.pipeline(
        pipeline_name="notion_pipeline", destination="duckdb", dev_mode=DEV_MODE
    )

    def column_name_projection(
        prop: DatabaseProperty, normalize: Callable[[str], str]
    ) -> str:
        result_name = normalize(prop.name)
        if result_name in [
            "my_column_name",
        ]:
            return None
        return result_name

    my_db = DatabaseResource(
        database_id="12345678912345678912345678912345",
        column_name_projection=column_name_projection,
    )

    data = source(
        limit=-1 if not DEV_MODE else 1,
        database_resources=[my_db],
    )
    info = pipeline.run(
        data,
        refresh="drop_sources" if DEV_MODE else None,
        # we need this in case new resources, etc. are added
        schema_contract={"columns": "evolve"},
    )
    print(info)


if __name__ == "__main__":
    load_notion_data()

from arroyo import exts, importer

class ImporterCronTask(exts.CronTask):
    interval = '1h'

    def run(self):
    	for origin in self.app.importer.get_origin_defs():
    		self.app.importer.import_origin(origin)


__arroyo_extensions__ = (
	('crontask', 'import', ImporterCronTask),
)

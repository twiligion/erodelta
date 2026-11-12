doc = """Erodelta sync module using EROFS images and xdelta3"""
__doc__ = doc

module_spec = {
    'name': 'erodelta',
    'description': doc,
    'provides': {
        'erodelta-module': {
            'name': 'erodelta',
            'sourcefile': 'erodelta',
            'class': 'ErodeltaSync',
            'description': doc,
            'functions': ['sync', 'new'],
            'func_desc': {
                'sync': 'Syncs the repository via EROFS delta',
                'new': 'Initializes a new repository',
            },
        }
    }
}

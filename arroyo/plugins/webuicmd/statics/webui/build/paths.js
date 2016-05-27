
const PATHS = {
    dist: {
        root: 'dist',
        app: 'dist/app',
        styles: 'dist/css'
    },
    src: {
        typescript: [
            "src/app/**/*.ts",
            "typings/index.d.ts"
        ],
        styles: "src/scss/**/*scss",
        static: [
            'src/systemjs.config.js',
            'src/index.html'
        ]
    }
};

module.exports = PATHS;

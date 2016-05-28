
const PATHS = {
    dist: {
        root: 'dist',
        app: 'dist/app',
        styles: 'dist/css',
        fonts: 'dist/fonts'
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
        ],
        fonts: [
            'bower_components/font-awesome/fonts/**/*'
        ]
    }
};

module.exports = PATHS;


import {Component, OnInit} from '@angular/core';
import {Router, Routes, ROUTER_DIRECTIVES} from '@angular/router';

import {ConfigComponent} from './config/config.component';
import {SearchComponent} from './search/search.component';

@Component({
    selector: 'arroyo-webui',
    templateUrl: window['STATIC_URL'] + 'app/templates/app.html',
    directives: [ROUTER_DIRECTIVES],
})
@Routes([
  {path: '/search', component: SearchComponent},
  {path: '/config', component: ConfigComponent},
])
export class AppComponent implements OnInit {
    title = "Arroyo Web UI";

    constructor(private router: Router) {}

    ngOnInit() {
        this.router.navigate(['/search']);
    }
}

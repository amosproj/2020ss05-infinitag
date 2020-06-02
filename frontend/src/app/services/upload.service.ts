import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders, HttpResponse, HttpErrorResponse } from '@angular/common/http';
import { environment } from './../../environments/environment';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';

import { IDocument } from './../models/IDocument.model'


/**
 *
 * @class UploadService
 *
 * Service handling uploading and updateing documents
 *
 */
@Injectable({
  providedIn: 'root'
})
export class UploadService {


  constructor(private httpClient: HttpClient) { }


  public postFile(file: File): Observable<object> {
      //console.log("postFile" + file.name)
      const formData: FormData = new FormData();
      formData.append('fileKey', file, file.name);
      //formData.append('test', 'abc');
      return this.httpClient
        .post(`${environment.serverUrl}/upload`, formData, {
          reportProgress: true,
          observe: 'events'
        });

  }

  public patchKeywords(iDoc: IDocument): Observable<object> {
    const httpOptions = {
      headers: new HttpHeaders({
        'Content-Type': 'application/json',
      })
    };

    return this.httpClient.patch(`${environment.serverUrl}/changekeywords`, iDoc, httpOptions);
  }


}
